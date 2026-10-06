# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from ..apps import App
from ..apps.submenu import run_submenu

_WIFI_TOOLS = (
    (
        "PORTAL",
        "Pico Portal",
        "portal.accessportal",
        "AccessPortal",
        "Captive portal",
        "/pico-portal-os/images/web.bin",
    ),
    (
        "CH.RADAR",
        "Channel Radar",
        "wifi.chradar",
        "ChannelRadar",
        "Channel interference",
        "/pico-portal-os/images/radar.bin",
    ),
    (
        "SERVICES",
        "mDNS/SSDP Sniffer",
        "wifi.mdnssniff",
        "MdnsSniff",
        "Discover LAN devices and services",
        "/pico-portal-os/images/target.bin",
    ),
    (
        "NET MON",
        "Network Monitor",
        "wifi.netwatch",
        "NetWatch",
        "AP activity timeline",
        "/pico-portal-os/images/network.bin",
    ),
    (
        "ANALYZER",
        "WiFi Analyzer",
        "wifi.wifianalyzer",
        "WifiAnalyzer",
        "Live spectrum waterfall",
        "/pico-portal-os/images/analyze.bin",
    ),
    (
        "WIFI SNIFF",
        "WiFi Sniffer",
        "wifi.wifisniff",
        "WifiSniff",
        "Seek nearby access points",
        "/pico-portal-os/images/target.bin",
    ),
)


class WifiTools(App):

    async def run(self, ctx):
        await run_submenu(ctx, "WIFI TOOLS", _WIFI_TOOLS)
