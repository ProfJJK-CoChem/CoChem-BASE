"""Run the student dashboard with authenticated, XSRF-protected kernel cleanup.

The upstream widgets manager sends a shutdown beacon when a rendered page is
closed. That beacon reads Tornado's standard ``_xsrf`` cookie. Standalone Voilà
does not otherwise need a form, so its rendered handler can finish the initial
GET without creating that cookie. Accessing ``xsrf_token`` before rendering
uses Tornado's supported cookie machinery; all upstream authentication and
XSRF verification remain in effect.
"""

from __future__ import annotations

import tornado.web
from voila.app import Voila
from voila.tornado.handler import TornadoVoilaHandler


class StudentRenderedHandler(TornadoVoilaHandler):
    """Issue the normal readable XSRF cookie before Voilà flushes its HTML."""

    @tornado.web.authenticated
    async def get(self, path=None):
        self.xsrf_token
        await super().get(path=path)


class StudentVoila(Voila):
    """Keep upstream routes, replacing only the supported rendered handler."""

    def init_handlers(self):
        handlers = super().init_handlers()
        replacements = 0
        result = []
        for entry in handlers:
            if entry[1] is TornadoVoilaHandler:
                entry = (entry[0], StudentRenderedHandler, *entry[2:])
                replacements += 1
            result.append(entry)
        if replacements == 0:
            raise RuntimeError("This Voilà version exposes no supported rendered-page handler")
        return result


if __name__ == "__main__":
    StudentVoila.launch_instance()
