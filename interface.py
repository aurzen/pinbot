from __future__ import annotations

import typing as ty
import aurflux
from aurflux.command import Response

import aurflux.auth
import discord
import asyncio
import subprocess
import aurcore as aur

if ty.TYPE_CHECKING:
   import datetime

VERSION = subprocess.check_output(["poetry", "version"]).decode().split(" ")[1]


class Interface(aurflux.cog.FluxCog):
   def load(self):
      @self.flux.router.listen_for(":message")
      @aur.Eventful.decompose
      async def _(message: discord.Message):
         if message.author == self.flux.user:
            return
         if isinstance(message.channel, discord.channel.DMChannel):
            embed = discord.Embed(
               title=f"Pinbot V{VERSION}",
               description=("Use ..help in your server for command details\n"
                            f"[Click me to add to your server](https://discord.com/oauth2/authorize?client_id={self.flux.user.id}&scope=bot&permissions=76816)\n"
                            f"[Get help here](https://s.ze.ax/d)")
            )
            await message.channel.send(embed=embed)

      @self._commandeer(name="setup", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def setup(ctx: aurflux.ty.GuildCommandCtx, args: str):
         """
         setup
         ==
         Runs the setup process
         ==
         ==
         :param ctx:
         :param args:
         :return:
         """
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         me = ctx.msg_ctx.guild.me
         try:
            print("setup!")
            if not ctx.msg_ctx.channel.permissions_for(me).add_reactions:
               yield Response(f"I need <add_reactions> in {ctx.msg_ctx.channel.mention}.")

            pinmap_orig = configs["pinmap"].copy()

            yield Response("Beginning setup... Type `cancel` to cancel setup without making changes", delete_after=30)

            header_resp = Response("Please select a pair of channels `#from-channel` to `#to-channel`\n"
                                   "Once there are `max` pinned messages in `#from-channel`, the next pin in `#from-channel` will cause the oldest pin to be converted to an embed and sent in `#to-channel`\n"
                                   # f"You can do this in the future without `{ctx.full_command}` via `{configs['prefix']}map #from #to`"
                                   )
            yield header_resp

            async def check_pair(ev: aurflux.FluxEvent) -> bool:
               m: discord.Message = ev.args[0]
               print(m)
               if m.author == m.guild.me:
                  return False
               if m.author != ctx.author_ctx.author:
                  return False
               if m.content.lower().strip() == "cancel":
                  return True
               if not m.channel_mentions:
                  return False
               s = aurflux.utils.find_mentions(m.content)
               return len(s) == 2

            assignment: discord.Message = (await self.flux.router.wait_for(":message", check_pair, timeout=45)).args[0]
            if assignment.content == "cancel":
               yield Response(f"Cancelled setup {aurflux.utils.EMOJI.check}, no changes have been made.")
               return

            from_channel_r, to_channel_r = aurflux.utils.find_mentions(assignment.content)
            from_channel, to_channel = self.flux.get_channel(from_channel_r), self.flux.get_channel(to_channel_r)

            def verify_channels():

               if not isinstance(from_channel, discord.TextChannel):
                  raise aurflux.CommandError(f"{from_channel_r} not recognized as a Text Channel. Please use a mention or an id.")
               if not isinstance(to_channel, discord.TextChannel):
                  raise aurflux.CommandError(f"{to_channel_r}  not recognized as a Text Channel. Please use a mention or an id.")

               from_perms = discord.Permissions(manage_channels=True)
               if not from_perms <= from_channel.permissions_for(me):
                  raise aurflux.errors.BotMissingPermissions(have=from_channel.permissions_for(me), need=from_perms)

               to_perms = discord.Permissions(send_messages=True, embed_links=True)
               if not to_perms <= to_channel.permissions_for(me):
                  raise aurflux.errors.BotMissingPermissions(have=from_channel.permissions_for(me), need=to_perms)

            verify_channels()

            resp = Response(f"Mapping pins from {from_channel.mention} to embeds in {to_channel.mention}", delete_after=30)

            yield resp
            try:
               await resp.message.add_reaction(aurflux.utils.EMOJI.check)
            except discord.errors.NotFound:
               pass

            resp = Response(f"What is the number of native discord pins you would like in {from_channel.mention}? [0-49]\n"
                            f"If you set this to 0, all pins will be immediately turned into embeds\n"
                            f"If you set this to any other number <= 49, {from_channel.mention} will hold that many native discord pins, "
                            f"after which the **oldest** pin will be turned into an embed")
            yield resp

            async def check_max(ev: aurflux.FluxEvent) -> bool:
               m: discord.Message = ev.args[0]
               if m.author == m.guild.me:
                  return False
               if m.author != m.author:
                  return False
               return True

            max_pins = None
            async for ev in self.flux.router.wait_for(":message", check_max, timeout=30, max_matches=None):
               message: discord.Message = ev.args[0]
               if message.author == self.flux.user:
                  continue
               if message.author != ctx.msg_ctx.author:
                  continue

               if message.content.strip() == "cancel":
                  yield Response("Cancelled. No changes made.")
                  async with self.flux.CONFIG.writeable_conf(ctx.config_identifier) as cfg:
                     cfg["pinmap"] = pinmap_orig
                  return

               try:
                  max_pins = int(message.content.strip())
                  if not (0 <= max_pins <= 49):
                     raise aurflux.errors.CommandError(f"The number of pins must be in [0,49].")
                  await message.add_reaction(aurflux.utils.EMOJI.check)
                  break
               except ValueError:
                  raise aurflux.errors.CommandError(f"`{message.content}` not recognized as a number.")

            async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
               cfg["pinmap"] = {**cfg.get("pinmap", {}), from_channel.id: to_channel.id}
               cfg["maxmap"] = {**cfg.get("maxmap", {}), from_channel.id: max_pins}

            if max_pins == 0:
               yield Response(f"Done! When a message is pinned in {from_channel.mention}, it will be converted into an embed in {to_channel.mention}")
            else:
               yield Response(f"Done! Once there are {max_pins} pins in {from_channel.mention}, the oldest pin will be converted to an embed in {to_channel.mention}")

         except asyncio.exceptions.TimeoutError:
            yield Response(f"Timed out! Stopping setup process. `{configs['prefix']}setup` to restart")

      @self._commandeer(name="maps", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def _(ctx: aurflux.ty.GuildCommandCtx, _):
         """
         maps
         ==ye
         Prints out the current set of maps
         ==
         ==
         :param ctx:
         :return:
         """
         configs = self.flux.CONFIG.of(ctx.msg_ctx)

         embed = discord.Embed(title="Pinbot Map")
         print(configs)
         pinmap = configs["pinmap"].items()
         if len(pinmap) == 0:
            embed.description = "No maps set!"
            return Response(embed=embed)

         embed.add_field(name="Map", value="\n".join(f"<#{f}>\t\u27F6\t<#{t}>" for f, t in pinmap), inline=True)
         embed.add_field(name="Max", value="\n".join(str(configs["maxmap"][f]) for f, _ in pinmap), inline=True)

         return Response(embed=embed)

      @self._commandeer(name="pinall", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def _(ctx: aurflux.ty.GuildCommandCtx, _):
         """
         pinall
         ==
         Forces a re-check of all mapped channels for pins
         ==
         ==
         :param ctx:
         :param _:
         :return:
         """
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         print(configs["pinmap"])
         for channel_id in configs["pinmap"]:
            await self.router.submit(event=aurflux.FluxEvent(self.flux, "aurflux:guild_channel_pins_update", self.flux.get_channel(int(channel_id)), None))
