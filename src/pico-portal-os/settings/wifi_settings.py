# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from ..apps import App
from ..apps.keyboard import edit_text
from ..storage import save_config


class WifiSettings(App):

    async def run(self, ctx):
        rows = ("DISCONNECT", "FORGET SAVED", "RECONNECT", "SCAN + CONNECT")
        sel = 0
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                sel = (sel - 1) % len(rows)
            if down:
                sel = (sel + 1) % len(rows)
            if select:
                action = rows[sel]
                if action == "DISCONNECT":
                    await self._disconnect(ctx)
                elif action == "FORGET SAVED":
                    self._forget(ctx)
                elif action == "RECONNECT":
                    await self._reconnect(ctx)
                else:
                    await self._wizard(ctx)
            self._draw_home(ctx, rows, sel)
            await uasyncio.sleep_ms(50)

    def _draw_home(self, ctx, rows, sel):
        crt = ctx.crt
        config = ctx.wifi_config
        crt.begin()
        title = "WiFi Settings" if crt.h > 160 else "WIFI SETTINGS"
        top = crt.ui_title(title)
        info = ctx.wifi.connection_info()
        if info:
            status = "ONLINE " + info[0]
        elif config.get("ssid"):
            status = "OFFLINE // SAVED"
        else:
            status = "OFFLINE // NO SAVED WIFI"
        status_scale = crt.fit_scale(status, crt.w - 16)
        crt.text_center(status, top, status_scale, "fg" if info else "dim")
        top += crt.text_height(status_scale) + 3
        if config.get("ssid"):
            saved = "SAVED: " + str(config["ssid"])[:24]
            saved_scale = crt.fit_scale(saved, crt.w - 16)
            crt.text_center(saved, top, saved_scale, "mid")
            top += crt.text_height(saved_scale) + 3
        descriptions = (
            "Stop station and turn radio off",
            "Erase saved credentials",
            "Retry the saved network",
            "Find and join a network",
        )
        crt.menu_rows(
            rows,
            sel,
            top,
            crt.ui_bottom(),
            x=8,
            descriptions=descriptions,
        )
        crt.button_hints(
            top_left="BACK",
            top_right="SEL",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    async def _disconnect(self, ctx):
        ctx.wifi.disconnect()
        await uasyncio.sleep_ms(100)
        if ctx.wifi.is_connected():
            await self._message(ctx, "DISCONNECT FAILED", "try again")
            return
        detail = (
            "saved network kept" if ctx.wifi_config.get("ssid") else "radio off"
        )
        await self._message(ctx, "DISCONNECTED", detail, 900)

    async def _reconnect(self, ctx):
        ssid = str(ctx.wifi_config.get("ssid", ""))
        password = str(ctx.wifi_config.get("password", ""))
        if not ssid:
            await self._message(ctx, "NOTHING SAVED", "use scan + connect")
            return

        self._notice(ctx, "RECONNECTING", ssid)
        try:
            ctx.wifi.reconnect(ssid, password)
        except Exception as exc:  # noqa: BLE001
            ctx.wifi.disconnect()
            await self._message(ctx, "RECONNECT FAILED", str(exc))
            return

        if await self._wait_for_connection(ctx, ssid):
            try:
                ctx.wifi.sync_time()
            except Exception:  # noqa: BLE001
                pass
            info = ctx.wifi.connection_info()
            await self._message(
                ctx, "RECONNECTED", info[0] if info else ssid, 900
            )
            return

        ctx.wifi.disconnect()
        await self._message(ctx, "TIMED OUT", "saved WiFi unavailable")

    async def _wizard(self, ctx):
        self._notice(ctx, "SCANNING", "finding networks...")
        try:
            aps = ctx.wifi.scan()
        except Exception as exc:  # noqa: BLE001
            await self._message(ctx, "SCAN FAILED", str(exc))
            return
        if not aps:
            await self._message(ctx, "NO NETWORKS", "top-left to return")
            return

        chosen = await self._choose_ap(ctx, aps)
        if chosen is None:
            return
        ssid, _bssid, _channel, _rssi, secured = chosen
        if not ssid:
            ssid = await edit_text(ctx, "NETWORK NAME", max_length=32)
            if not ssid:
                return
        password = ""
        if secured:
            password = await edit_text(ctx, "WIFI PASSWORD", secret=True)
            if password is None:
                return

        self._notice(ctx, "CONNECTING", ssid)
        try:
            ctx.wifi.connect(ssid, password)
        except Exception as exc:  # noqa: BLE001
            await self._message(ctx, "CONNECT FAILED", str(exc))
            return

        if await self._wait_for_connection(ctx, ssid):
            ctx.wifi_config["ssid"] = ssid
            ctx.wifi_config["password"] = password
            try:
                save_config(ctx.config)
            except Exception:  # noqa: BLE001
                pass
            try:
                ctx.wifi.sync_time()
            except Exception:  # noqa: BLE001
                pass
            await self._message(
                ctx, "CONNECTED", ctx.wifi.connection_info()[0], 900
            )
            return
        ctx.wifi.disconnect()
        await self._message(ctx, "TIMED OUT", "check password")

    async def _wait_for_connection(self, ctx, ssid, timeout_ms=15000):
        started = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), started) < timeout_ms:
            if ctx.wifi.is_connected():
                return True
            self._notice(ctx, "CONNECTING", ssid)
            await uasyncio.sleep_ms(250)
        return False

    async def _choose_ap(self, ctx, aps):
        sel = 0
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return None
            if up:
                sel = (sel - 1) % len(aps)
            if down:
                sel = (sel + 1) % len(aps)
            if select:
                return aps[sel]

            crt = ctx.crt
            selected_ap = aps[sel]
            detail = "CH {}  {} dBm".format(selected_ap[2], selected_ap[3])
            labels = tuple(
                ("# " if ap[4] else "  ") + ((ap[0] or "<hidden>")[:16])
                for ap in aps
            )
            crt.begin()
            top = crt.ui_title("SELECT NETWORK")
            detail_scale = crt.fit_scale(detail, crt.w - 16)
            crt.text_center(detail, top, detail_scale, "mid")
            top += crt.text_height(detail_scale) + 3
            crt.menu_rows(labels, sel, top, crt.ui_bottom())
            crt.button_hints(
                top_left="BACK",
                top_right="SEL",
                bottom_left="UP",
                bottom_right="DWN",
            )
            crt.end()
            await uasyncio.sleep_ms(50)

    def _forget(self, ctx):
        ctx.wifi.disconnect()
        ctx.wifi_config["ssid"] = ""
        ctx.wifi_config["password"] = ""
        try:
            save_config(ctx.config)
        except Exception:  # noqa: BLE001
            pass

    def _notice(self, ctx, title, detail):
        ctx.lamp.status("info")
        crt = ctx.crt
        crt.begin()
        crt.text_center(title, crt.h // 2 - 15, 2, "hi")
        crt.text_center(str(detail)[:28], crt.h // 2 + 12, 1, "mid")
        crt.end()

    async def _message(self, ctx, title, detail, duration=0):
        if "FAILED" in title or title == "TIMED OUT":
            kind = "error"
        elif title in ("CONNECTED", "RECONNECTED", "DISCONNECTED"):
            kind = "success"
        else:
            kind = "warning"
        await ctx.lamp.feedback(kind)
        ctx.lamp.status(kind)
        started = time.ticks_ms()
        try:
            while True:
                _up, _down, _select, back = ctx.input.poll()
                if back or (
                    duration
                    and time.ticks_diff(time.ticks_ms(), started) >= duration
                ):
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
