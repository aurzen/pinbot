from __future__ import annotations

import typing as ty
import aurflux
from aurflux.response import Response
import discord
import asyncio
from aurflux.argh import arghify, Arg, ChannelIDType
import subprocess

if ty.TYPE_CHECKING:
    import datetime

VERSION = subprocess.check_output(["poetry", "version"]).decode().split(" ")[1]


class Interface(aurflux.AurfluxCog):
    listening_channels = set()

    def route(self):
        @self.register
        @self.aurflux.router.endpoint(":message", decompose=True)
        async def _(message: discord.Message):
            if message.author == self.aurflux.user:
                return
            if isinstance(message.channel, discord.channel.DMChannel):
                embed = discord.Embed(
                    title=f"Pinbot V{VERSION}",
                    description="Use ..help in your server for command details\n" \
                                f"[Click me to add to your server](https://discord.com/oauth2/authorize?client_id={self.aurflux.user.id}&scope=bot&permissions=76816)"
                )
                await Response(embed=embed).execute(aurflux.MessageContext(bot=self.aurflux, message=message))

        @self.register
        @aurflux.CommandCheck.has_permissions(discord.Permissions(manage_guild=True))
        @self.aurflux.commandeer(name="setup", parsed=False)
        async def setup(ctx: aurflux.MessageContext, args: str):
            """
            setup
            :param ctx:
            :param args:
            :return:
            """
            configs = self.aurflux.CONFIG.of(ctx)
            try:
                print("setup!")
                yield Response("Beginning setup... Type `done` to end setup", delete_after=30)

                header_resp = Response("Please select a pair of channels `#from-channel` to `#to-channel`\n"
                                       "Once there are `max` pinned messages in `#from-channel`, the next pin in `#from-channel` will cause the oldest pin to be converted to an embed and sent in `#to-channel`\n"
                                       # f"You can do this in the future without `{ctx.full_command}` via `{configs['prefix']}map #from #to`"
                                       )
                yield header_resp

                async def check_pair(ev: aurflux.AurfluxEvent) -> bool:
                    m: discord.Message = ev.args[0]
                    print(m)
                    if m.author == m.guild.me:
                        return False
                    if m.author != ctx.author:
                        return False
                    if m.content in ("cancel", "done"):
                        return True
                    if not m.channel_mentions:
                        return False
                    s = aurflux.utils.find_mentions(m.content)
                    return len(s) == 2 or m.content == "done"

                assignment: discord.Message = (await self.aurflux.router.wait_for(":message", check_pair, timeout=45)).args[0]
                if assignment.content == "cancel":
                    yield Response(f"Finished setup {aurflux.utils.EMOJIS['white_check_mark']}")
                    return

                if assignment.content == "done":
                    yield Response(f"Finished setup {aurflux.utils.EMOJIS['white_check_mark']}")
                    return

                from_channel, to_channel = aurflux.utils.find_mentions(assignment.content)
                from_channel, to_channel = self.aurflux.get_channel(from_channel), self.aurflux.get_channel(to_channel)
                # try:
                #     await assignment.delete()
                # except discord.errors.Forbidden:
                #     raise aurflux.errors.BotMissingPermissions(discord.Permissions())
                resp = Response(f"Mapping pins from {from_channel.mention} to embeds in {to_channel.mention}", delete_after=30)
                yield resp

                async with self.aurflux.CONFIG.writeable_conf(ctx.config_identifier) as cfg:
                    cfg["pinmap"] = {**cfg.get("pinmap", {}), from_channel.id: to_channel.id}
                await resp.message.add_reaction(aurflux.utils.EMOJIS["white_check_mark"])

                resp = Response(f"What is the number of native discord pins you would like in {from_channel.mention}? [0-49]\n"
                                f"If you set this to 0, all pins will be immediately turned into embeds\n"
                                f"If you set this to any other number <= 49, {from_channel.mention} will hold that many native discord pins, "
                                f"after which the **oldest** pin will be turned into an embed")
                yield resp

                async def check_max(ev: aurflux.AurfluxEvent) -> bool:
                    m: discord.Message = ev.args[0]
                    if m.author == m.guild.me:
                        return False
                    if m.author != m.author:
                        return False
                    return True

                while True:
                    max_resp: discord.Message = (await self.aurflux.router.wait_for(":message", check_max, timeout=45)).args[0]
                    if max_resp.author == self.aurflux.user:
                        continue
                    try:
                        max_pins = int(max_resp.content)
                        if not 0 <= max_pins <= 49:
                            raise ValueError
                        break
                    except ValueError:
                        yield Response("Please enter a number <= 49 and >= 0", delete_after=10)

                async with self.aurflux.CONFIG.writeable_conf(ctx.config_identifier) as cfg:
                    cfg["maxmap"] = {**cfg.get("maxmap", {}), from_channel.id: max_pins}

                await max_resp.add_reaction(aurflux.utils.EMOJIS["white_check_mark"])
                if max_pins == 0:
                    yield Response(f"Done! When a message is pinned in {from_channel.mention}, it will be converted into an embed in {to_channel.mention}")
                else:
                    yield Response(f"Done! Once there are {max_pins} pins in {from_channel.mention}, the oldest pin will be converted to an embed in {to_channel.mention}")
            except asyncio.exceptions.TimeoutError:
                yield Response(f"Timed out! Stopping setup process. `{configs['prefix']}setup` to restart")

        @self.register
        @self.aurflux.commandeer(name="maps", parsed=False)
        async def _(ctx: aurflux.MessageContext, _):
            """
            Prints out the current set of maps
            :param ctx:
            :return:
            """
            configs = self.aurflux.CONFIG.of(ctx)

            embed = discord.Embed(title="Pinbot Map")
            pinmap = configs["pinmap"].items()
            print(len(pinmap))
            if len(pinmap) == 0:
                embed.description = "No maps set!"
                return Response(embed=embed)

            embed.add_field(name="Map", value="\n".join(f"<#{f}> \u27F6 <#{t}>" for f, t in pinmap), inline=True)
            embed.add_field(name="Max", value="\n".join(str(configs["maxmap"][f]) for f, _ in pinmap), inline=True)

            return Response(embed=embed)
