# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import sys

from ..apps import App


def _drop_module(name):
    sys.modules.pop(name, None)
    parent = sys.modules.get("pico-portal-os.portal")
    child = name.rsplit(".", 1)[-1]
    if parent is not None and hasattr(parent, child):
        delattr(parent, child)


class AccessPortal(App):

    async def run(self, ctx):
        while True:
            action = await self._run_dynamic(
                ctx,
                "pico-portal-os.portal.portalmenu",
                "PortalMenu",
            )
            if action != "start":
                return
            await self._run_dynamic(
                ctx,
                "pico-portal-os.portal.portalserver",
                "PortalServer",
            )

    async def _run_dynamic(self, ctx, name, class_name):
        module = None
        instance = None
        gc.collect()
        try:
            module = __import__(name, None, None, (class_name,))
            instance = getattr(module, class_name)()
            return await instance.run(ctx)
        finally:
            if instance is not None:
                del instance
            if module is not None:
                del module
            _drop_module(name)
            gc.collect()
