from __future__ import annotations

import asyncio
import contextlib
import logging
import aurflux
# import aiohttp
import aurcore
from interface import Interface
from pin_handler import PinHandler
import typing as ty
import TOKENS

log = logging.Logger("a")
log.setLevel(logging.DEBUG)

if ty.TYPE_CHECKING:
    from aurflux.context import MessageCtx


class Pinbot:
    def __init__(self):
        self.event_router = aurcore.event.EventRouterHost(name=self.__class__.__name__.lower())
        self.flux = aurflux.FluxClient("pinbot", admin_id=TOKENS.ADMIN_ID, parent_router=self.event_router, status="..help | s.ze.ax/d for help")

    async def startup(self, token: str):
        await self.flux.start(token)

    async def shutdown(self):
        await self.flux.logout()


pinbot = Pinbot()





pinbot.flux.register_cog(PinHandler)
pinbot.flux.register_cog(Interface)

aurcore.aiorun(pinbot.startup(token=TOKENS.PINBOT), pinbot.shutdown())
