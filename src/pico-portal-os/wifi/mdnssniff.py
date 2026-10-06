# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_MDNS_GROUP = "224.0.0.251"
_MDNS_PORT = 5353
_SSDP_GROUP = "239.255.255.250"
_SSDP_PORT = 1900

_CAP = 16
_SERVICES = 5
_PACKETS_PER_FRAME = 6
_BUFFER = 1024

_DISCOVERY_WARMUPS = 3
_DISCOVERY_WARMUP_MS = 4_000
_DISCOVERY_INTERVAL_MS = 60_000

_MDNS_QUERY_NAMES = (
    "_services._dns-sd._udp.local",
    "_googlecast._tcp.local",
    "_airplay._tcp.local",
    "_raop._tcp.local",
    "_ipp._tcp.local",
    "_ipps._tcp.local",
    "_http._tcp.local",
    "_workstation._tcp.local",
    "_smb._tcp.local",
)

_SSDP_MSEARCH = (
    b"M-SEARCH * HTTP/1.1\r\n"
    b"HOST: 239.255.255.250:1900\r\n"
    b'MAN: "ssdp:discover"\r\n'
    b"MX: 2\r\n"
    b"ST: ssdp:all\r\n"
    b"\r\n"
)

_IPPROTO_IP = 0
_IP_ADD_MEMBERSHIP = 3
_IP_MULTICAST_TTL = 5
_IP_MULTICAST_IF = 9

_NOT_A_SERVICE = ("_tcp", "_udp", "_services", "_dns-sd")


def _packed_ip(text):
    """Pack a dotted-quad string into 4 bytes for an lwIP ip_mreq."""
    return bytes(int(part) for part in text.split("."))


def _encode_dns_name(name):
    """Encode a dotted DNS name as length-prefixed labels, no compression."""
    encoded = bytearray()
    for label in name.split("."):
        raw = label.encode()
        encoded.append(len(raw))
        encoded.extend(raw)
    encoded.append(0)
    return encoded


def _build_mdns_query(names):
    """Build one mDNS packet carrying a PTR question for each name."""
    packet = bytearray(12)
    packet[4] = (len(names) >> 8) & 0xFF
    packet[5] = len(names) & 0xFF
    for name in names:
        packet.extend(_encode_dns_name(name))
        packet.extend(b"\x00\x0c\x80\x01")
    return bytes(packet)


def _dns_name(packet, offset, hops=6):
    """Read a DNS name, following compression pointers.

    Returns (name, next_offset). next_offset is the position just past the name
    as it was written here, which is not where a followed pointer landed.
    """
    labels = []
    total = len(packet)
    after = None
    while hops > 0:
        if offset >= total:
            break
        length = packet[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= total:
                break
            if after is None:
                after = offset + 2
            offset = (length & 0x3F) << 8 | packet[offset + 1]
            hops -= 1
            continue
        start = offset + 1
        end = start + length
        if end > total:
            break
        try:
            labels.append(bytes(packet[start:end]).decode())
        except Exception:  # noqa: BLE001
            labels.append("?")
        offset = end
    return ".".join(labels), after if after is not None else offset


def _service_label(name):
    """Pull the bare service out of a `_googlecast._tcp.local` style name.

    `_services._dns-sd._udp` is the meta-query we send, not a service anyone
    offers, so it returns "" and lets the caller fall back to the PTR target.
    """
    for part in name.split("."):
        if part.startswith("_") and part not in _NOT_A_SERVICE:
            return part[1:][:14]
    return ""


def _instance_label(name):
    """
    Return the human instance label, or "" when the name is a service type.
    """
    first = name.split(".")[0]
    if not first or first.startswith("_"):
        return ""
    return first.replace("\\032", " ")[:24]


def _parse_mdns(packet):
    """Return (instance, host, services) announced by one mDNS packet."""
    if len(packet) < 12:
        return "", "", ()
    questions = packet[4] << 8 | packet[5]
    answers = packet[6] << 8 | packet[7]
    authority = packet[8] << 8 | packet[9]
    additional = packet[10] << 8 | packet[11]
    records = answers + authority + additional
    offset = 12
    for _ in range(questions):
        _name, offset = _dns_name(packet, offset)
        offset += 4  # qtype + qclass
    instance = ""
    host = ""
    services = []
    total = len(packet)
    for _ in range(records):
        name, offset = _dns_name(packet, offset)
        if offset + 10 > total:
            break
        rtype = packet[offset] << 8 | packet[offset + 1]
        rdlength = packet[offset + 8] << 8 | packet[offset + 9]
        offset += 10
        end = offset + rdlength
        if end > total:
            break
        if rtype == 12:
            target, _ = _dns_name(packet, offset)
            instance = instance or _instance_label(target)
            service = _service_label(name) or _service_label(target)
            if service and service not in services:
                services.append(service)
        elif rtype == 33:
            instance = instance or _instance_label(name)
            service = _service_label(name)
            if service and service not in services:
                services.append(service)
        elif rtype == 1 and rdlength == 4:
            host = host or _instance_label(name)
        offset = end
    return instance, host, tuple(services[:_SERVICES])


def _short_urn(value):
    """Shorten a UPnP URN or USN to the part worth reading on a small screen."""
    if value.startswith("urn:"):
        parts = value.split(":")
        if len(parts) >= 4:
            return parts[-2][:14]
    if value.startswith("uuid:"):
        return ""
    return (value.split(":")[-1] if ":" in value else value)[:14]


def _parse_ssdp(packet):
    """Return (label, service) from an SSDP announcement, or ("", "").

    M-SEARCH datagrams are someone else's question, not a device describing
    itself, so they are ignored.
    """
    try:
        text = bytes(packet).decode()
    except Exception:  # noqa: BLE001
        return "", ""
    lines = text.split("\r\n")
    if not lines or lines[0].upper().startswith("M-SEARCH"):
        return "", ""
    label = ""
    service = ""
    for line in lines[1:]:
        head, sep, value = line.partition(":")
        if not sep:
            continue
        head = head.strip().upper()
        value = value.strip()
        if head == "SERVER" and not label:
            for token in reversed(value.split()):
                if "/" in token and not token.upper().startswith("UPNP"):
                    label = token.split("/")[0][:20]
                    break
        elif head in ("NT", "ST") and not service:
            service = _short_urn(value)
        elif head == "USN" and not service:
            service = _short_urn(value)
    return label, service


class MdnsSniff(App):

    async def run(self, ctx):
        info = ctx.wifi.connection_info()
        if not info:
            await self._offline(ctx)
            return

        local_ip = info[0]
        sockets = []
        joined = 0
        for group, port, ttl in (
            (_MDNS_GROUP, _MDNS_PORT, 255),
            (_SSDP_GROUP, _SSDP_PORT, 4),
        ):
            sock, member = self._listen(group, port, local_ip, ttl)
            if sock is not None:
                sockets.append((sock, port))
                joined += 1 if member else 0

        devices = {}
        counts = [0, 0, 0]
        last_probe = 0
        sel = 0
        mode = "LIST"
        try:
            if not sockets:
                await self._failed(ctx)
                return
            while True:
                up, down, select, back = ctx.input.poll()
                order = sorted(devices.keys())

                if mode == "LIST":
                    if back:
                        return
                    if up:
                        sel = (sel - 1) % max(1, len(order))
                    if down:
                        sel = (sel + 1) % max(1, len(order))
                    if select:
                        if order:
                            sel = min(sel, len(order) - 1)
                            mode = "DETAIL"
                            continue
                        counts[2] = 0  # nothing found
                    self._draw_list(
                        ctx, order, devices, counts, sel, joined, local_ip
                    )
                else:
                    if back or select:
                        mode = "LIST"
                        continue
                    if (up or down) and order:
                        sel = (sel + (1 if down else -1)) % len(order)
                    self._draw_detail(ctx, order, devices, sel)

                now = time.ticks_ms()
                due = (
                    _DISCOVERY_WARMUP_MS
                    if counts[2] < _DISCOVERY_WARMUPS
                    else _DISCOVERY_INTERVAL_MS
                )
                if counts[2] == 0 or time.ticks_diff(now, last_probe) >= due:
                    self._send_discovery(sockets, counts)
                    last_probe = now

                self._pump(sockets, devices, counts, local_ip)
                await uasyncio.sleep(0.05)
        finally:
            for sock, _port in sockets:
                try:
                    sock.close()
                except Exception:  # noqa: BLE001
                    pass
            del sockets
            devices.clear()
            gc.collect()

    def _listen(self, group, port, local_ip, ttl):
        """
        Bind a listening UDP socket and join `group`. Returns (sock, joined).
        """
        import socket

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:  # noqa: BLE001
                pass
            sock.bind(("0.0.0.0", port))
            sock.setblocking(False)
        except Exception as exc:  # noqa: BLE001
            print("mdnssniff: bind failed", port, repr(exc))
            if sock is not None:
                try:
                    sock.close()
                except Exception:  # noqa: BLE001
                    pass
            return None, False
        try:
            sock.setsockopt(_IPPROTO_IP, _IP_MULTICAST_TTL, ttl)
        except Exception:  # noqa: BLE001
            pass
        try:
            sock.setsockopt(_IPPROTO_IP, _IP_MULTICAST_IF, _packed_ip(local_ip))
        except Exception:  # noqa: BLE001
            pass
        try:
            sock.setsockopt(
                _IPPROTO_IP,
                _IP_ADD_MEMBERSHIP,
                _packed_ip(group) + _packed_ip(local_ip),
            )
            return sock, True
        except Exception as exc:  # noqa: BLE001
            print("mdnssniff: join failed", group, port, local_ip, repr(exc))
            return sock, False

    def _send_discovery(self, sockets, counts):
        """Ask each group the standard discovery question."""
        query = _build_mdns_query(_MDNS_QUERY_NAMES)
        for sock, port in sockets:
            try:
                if port == _MDNS_PORT:
                    sock.sendto(query, (_MDNS_GROUP, _MDNS_PORT))
                else:
                    sock.sendto(_SSDP_MSEARCH, (_SSDP_GROUP, _SSDP_PORT))
            except OSError as exc:
                print("mdnssniff: probe failed", port, repr(exc))
        del query
        counts[2] += 1

    def _pump(self, sockets, devices, counts, local_ip):
        """Drain a bounded number of waiting datagrams into the device table."""
        for sock, port in sockets:
            for _ in range(_PACKETS_PER_FRAME):
                try:
                    packet, address = sock.recvfrom(_BUFFER)
                except OSError:
                    break  # nothing buffered
                if not packet:
                    break
                source = address[0] if address else ""
                if source == local_ip:
                    continue
                if port == _MDNS_PORT:
                    counts[0] += 1
                    instance, host, services = _parse_mdns(packet)
                    label = instance or host
                    kind = "mdns"
                else:
                    counts[1] += 1
                    label, service = _parse_ssdp(packet)
                    services = (service,) if service else ()
                    kind = "ssdp"
                del packet
                if source:
                    self._merge(devices, source, label, services, kind)

    def _merge(self, devices, source, label, services, kind):
        entry = devices.get(source)
        if entry is None:
            if len(devices) >= _CAP:
                return
            entry = [label, [], 0, 0, 0]
            devices[source] = entry
        elif label and not entry[0]:
            entry[0] = label
        for service in services:
            if service and service not in entry[1]:
                if len(entry[1]) < _SERVICES:
                    entry[1].append(service)
        entry[2 if kind == "mdns" else 3] += 1
        entry[4] = time.ticks_ms()

    def _draw_list(self, ctx, order, devices, counts, sel, joined, local_ip):
        crt = ctx.crt
        crt.begin()
        title = "mDNS/SSDP Sniffer" if crt.h > 160 else "MDNS/SSDP"
        crt.text_center("{}  {}".format(title, len(order)), 3, 1, "hi")
        crt.hline(CELL + 5, "dim")

        head_y = CELL + 8
        crt.text(
            "mDNS {}".format(counts[0]),
            6,
            head_y,
            1,
            "fg" if counts[0] else "dim",
        )
        crt.text(
            "SSDP {}".format(counts[1]),
            6 + (crt.w - 12) // 3,
            head_y,
            1,
            "fg" if counts[1] else "dim",
        )
        crt.text_right(local_ip, crt.w - 6, head_y, 1, "dim")

        row_h = CELL + 3
        top_y = head_y + CELL + 4
        visible = max(1, (crt.h - top_y - CELL - 2) // row_h)
        start = 0
        if sel >= visible:
            start = sel - visible + 1

        if not order:
            if joined:
                crt.text(
                    "asked {}x, listening".format(counts[2]), 6, top_y, 1, "mid"
                )
                crt.text(
                    "replies land within seconds", 6, top_y + row_h, 1, "dim"
                )
                crt.text(
                    "if the LAN passes multicast",
                    6,
                    top_y + 2 * row_h,
                    1,
                    "dim",
                )
            else:
                crt.text("no multicast group join", 6, top_y, 1, "warn")
                crt.text(
                    "firmware lacks IGMP support", 6, top_y + row_h, 1, "dim"
                )
                crt.text(
                    "reason printed to the REPL", 6, top_y + 2 * row_h, 1, "dim"
                )

        for i in range(visible):
            index = start + i
            if index >= len(order):
                break
            source = order[index]
            label, services, mdns, ssdp, _last = devices[source]
            y = top_y + i * row_h
            pen = "hi" if index == sel else "mid"
            if index == sel:
                crt.use("dim")
                crt.g.rectangle(2, y - 1, crt.w - 4, row_h - 1)
            crt.text(source, 6, y, 1, pen)
            detail = label or (services[0] if services else "")
            if not detail:
                detail = "mDNS" if mdns else "SSDP"
            crt.text(crt.clip_text(detail, crt.w - 116, 1), 112, y, 1, pen)

        ctx.lamp.set((0, 140, 160) if order else (0, 70, 90))
        crt.button_hints(
            top_left="BACK",
            top_right="INFO" if order else "PROBE",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    def _draw_detail(self, ctx, order, devices, sel):
        crt = ctx.crt
        crt.begin()
        top = crt.ui_title("DEVICE")
        if not order:
            crt.text_center("no devices", crt.h // 2, 1, "mid")
            crt.button_hints(top_left="BACK", top_right="LIST")
            crt.end()
            return

        sel = min(sel, len(order) - 1)
        source = order[sel]
        label, services, mdns, ssdp, last = devices[source]
        age = time.ticks_diff(time.ticks_ms(), last) // 1000

        crt.text(source, 8, top, 2, "fg")
        y = top + crt.text_height(2) + 4
        crt.text(
            crt.clip_text(label or "<no name given>", crt.w - 16, 1),
            8,
            y,
            1,
            "hi",
        )
        y += CELL + 5

        crt.text("SERVICES", 8, y, 1, "mid")
        y += CELL + 2
        if services:
            for service in services:
                if y > crt.ui_bottom() - 3 * CELL:
                    break
                crt.text("- " + service, 12, y, 1, "fg")
                y += CELL + 1
        else:
            crt.text("- none decoded yet", 12, y, 1, "dim")
            y += CELL + 1

        y += 3
        crt.text("mDNS {}  SSDP {}".format(mdns, ssdp), 8, y, 1, "mid")
        y += CELL + 2
        crt.text("last heard {}s ago".format(age), 8, y, 1, "dim")

        crt.button_hints(
            top_left="BACK",
            top_right="LIST",
            bottom_left="PREV",
            bottom_right="NEXT",
        )
        crt.end()

    async def _offline(self, ctx):
        await self._notice(
            ctx,
            "NO NETWORK",
            "Join WiFi in Settings",
            "announcements are LAN-only",
        )

    async def _failed(self, ctx):
        await self._notice(
            ctx,
            "PORTS BUSY",
            "5353 and 1900 unavailable",
            "leave and re-enter to retry",
        )

    async def _notice(self, ctx, headline, first, second):
        crt = ctx.crt
        ctx.lamp.set((120, 60, 0))
        while True:
            if any(ctx.input.poll()):
                ctx.lamp.set((0, 70, 30))
                return
            crt.begin()
            crt.text_center(
                "mDNS/SSDP Sniffer" if crt.h > 160 else "MDNS/SSDP", 3, 1, "hi"
            )
            crt.hline(CELL + 5, "dim")
            crt.text_center(headline, crt.h // 2 - 16, 2, "warn")
            crt.text_center(first, crt.h // 2 + 8, 1, "mid")
            crt.text_center(second, crt.h // 2 + 8 + CELL + 2, 1, "dim")
            crt.button_hints(top_left="BACK")
            crt.end()
            await uasyncio.sleep(0.05)
