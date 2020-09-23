from __future__ import annotations

import asyncio
import contextlib
import logging
import aurflux
# import aiohttp
import aurcore
from interface import Interface
from pin_handler import PinHandler
from aurflux.argh import *
import TOKENS

log = logging.Logger("a")
log.setLevel(logging.DEBUG)

if ty.TYPE_CHECKING:
    from aurflux.context import MessageContext


class Pinbot:
    def __init__(self):
        self.event_router = aurcore.event.EventRouter(name="roombot")
        self.aurflux = aurflux.Aurflux("pinbot", admin_id=TOKENS.ADMIN_ID, parent_router=self.event_router, builtins=False)
        print("init!")

        @self.aurflux.router.endpoint(":ready")
        def rdy(event: aurcore.event.Event):
            print("Ready!")

    async def startup(self, token: str):
        await self.aurflux.start(token)

    async def shutdown(self):
        await self.aurflux.logout()


pinbot = Pinbot()





pinbot.aurflux.register_cog(PinHandler)
pinbot.aurflux.register_cog(Interface)
aurcore.aiorun(pinbot.startup(token=TOKENS.PINBOT), pinbot.shutdown())
