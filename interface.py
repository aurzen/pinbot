from __future__ import annotations

import typing as ty
import aurflux
from aurflux.command import Response

import aurflux.auth
import discord
import base64
import asyncio as aio
import subprocess
import aurcore as aur
import collections as clc
import functools as fnt
import itertools as itt
import pickle
from loguru import logger

aur.log.setup()

if ty.TYPE_CHECKING:
   import datetime

VERSION = subprocess.check_output(["poetry", "version"]).decode().split(" ")[1]


class Interface(aurflux.cog.FluxCog):
   def load(self):
      async def verify_channel_pair(from_id, to_id):
         from_channel, to_channel = self.flux.get_channel(from_id), self.flux.get_channel(to_id)

         if not isinstance(from_channel, discord.TextChannel):
            raise ValueError(f"{from_id} not recognized as a Text Channel")
            # raise aurflux.CommandError(f"{from_id} not recognized as a Text Channel. Please use a mention or an id.")
         if not isinstance(to_channel, discord.TextChannel):
            raise ValueError(f"{from_id} not recognized as a Text Channel")
            # raise aurflux.CommandError(f"{to_id}  not recognized as a Text Channel. Please use a mention or an id.")

         aurflux.utils.perm_check(from_channel, discord.Permissions(manage_messages=True, read_messages=True))
         aurflux.utils.perm_check(to_channel, discord.Permissions(embed_links=True, send_messages=True))
         return from_channel, to_channel

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
                            f"[Get help here](https://s.ze.ax/d)\n"
                            f"If you are upgrading from v1, you can use `..upgrade` to import settings")
            )
            await message.channel.send(embed=embed)

      @self._commandeer(name="setup", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __setup(ctx: aurflux.ty.GuildCommandCtx, args: str):
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
            if (pinbot_v1 := await self.flux.get_member_s(ctx.msg_ctx.guild, 535572077118488576)):
               yield Response(f"{pinbot_v1.mention} found. If you would like to automatically import settings, please say `cancel` and then `{configs['prefix']}import`")

            if not ctx.msg_ctx.channel.permissions_for(me).add_reactions:
               yield Response(f"I need <add_reactions> in {ctx.msg_ctx.channel.mention}.")

            pinmap_orig = configs["pinmap"].copy()

            yield Response("Beginning setup... Type `cancel` to cancel setup without making changes", delete_after=30)

            header_resp = Response("Please select a pair of channels `#from-channel` to `#to-channel`\n"
                                   "Once there are `max` pinned messages in `#from-channel`, the next pin in `#from-channel` will cause the oldest pin to be converted to an embed and sent in `#to-channel`\n"
                                   # f"You can do this in the future without `{ctx.full_command}` via `{configs['prefix']}map #from #to`"
                                   )
            yield header_resp

            async def check_pair(check_ev: aurflux.FluxEvent) -> bool:
               m: discord.Message = check_ev.args[0]
               if not m.guild:
                  return False
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

            # <editor-fold desc="Check Channels & Perms">
            from_channel_r, to_channel_r = aurflux.utils.find_mentions(assignment.content)
            try:
               from_channel, to_channel = await verify_channel_pair(from_channel_r, to_channel_r)
            except ValueError as e:
               raise aurflux.CommandError(f"{e}. Please use a mention or an id.")

            resp = Response(f"Mapping pins from {from_channel.mention} to embeds in {to_channel.mention}", delete_after=30)
            yield resp
            # </editor-fold>

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
               if not message.content:
                  continue
               if message.content.strip() == "cancel":
                  yield Response("Cancelled. No changes made.")
                  async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
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

            yield Response(f"Would you like the oldest or newest pin in the channel to be converted to an embed upon reaching {max_pins} pins?\n`oldest` or `newest`")

            old_new = "oldest"
            async for ev in self.flux.router.wait_for(":message", check_max, timeout=30, max_matches=None):
               message: discord.Message = ev.args[0]
               if message.author == self.flux.user:
                  continue
               if message.author != ctx.msg_ctx.author:
                  continue
               if not message.content:
                  continue
               if (old_new := message.content.strip().lower()) in ["oldest", "newest"]:
                  yield Response(f"Set to {old_new}")
                  async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
                     cfg["newestmap"][from_channel.id] = old_new == "newest"
                  break

               raise aurflux.errors.CommandError(f"`{message.content}` is not `oldest` or `newest`.")

            if max_pins == 0:
               yield Response(f"Done! When a message is pinned in {from_channel.mention}, it will be converted into an embed in {to_channel.mention}")
            else:
               yield Response(f"Done! Once there are {max_pins} pins in {from_channel.mention}, the {old_new} pin will be converted to an embed in {to_channel.mention}")

         except aio.exceptions.TimeoutError:
            yield Response(f"Timed out! Stopping setup process. `{configs['prefix']}setup` to restart")

      @self._commandeer(name="maps", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __maps(ctx: aurflux.ty.GuildCommandCtx, _):
         """
         maps
         ==
         Prints out the current set of maps
         ==
         ==
         :param ctx:
         :return:
         """
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         embeds = clc.defaultdict(discord.Embed)
         embeds[0].title = "Pinbot Map"
         # embed = discord.Embed(title="Pinbot Map")
         pinmap = configs["pinmap"].items()
         if len(pinmap) == 0:
            embeds[0].description = "No maps set!"


         maps = []
         maxes = [str(configs["maxmap"][f]) for f, _ in pinmap]

         for f, t in pinmap:
            f_c = await self.flux.get_channel_s(f)
            f_text = f_c.mention if f_c else f"`{f}`"
            t_c = await self.flux.get_channel_s(t)
            t_text = t_c.mention if t_c else f"`{t}`"
            maps.append(f"{f_text}\t\u27F6\t{t_text}")

         lengths = itt.accumulate([len(m) + len(f) for m, f in zip(maps, maxes)])

         def join_text(a: ty.List[ty.Tuple[str, str]],b: ty.Tuple[str, str]):
            b = (b[0], b[1] + len(b[0])//30 * "\n")
            if sum(map(len, a[-1])) >= 1000:
               return a + [b]
            else:
               return [*a[:-1], (f"{a[-1][0]}\n{b[0]}", f"{a[-1][1]}\n{b[1]}")]


         embed_blocks = fnt.reduce(join_text, zip(maps, maxes), [("","")])
         for index, (map_block, max_block) in enumerate(embed_blocks):

            embeds[index].add_field(name="Map", value=map_block, inline=True)

            embeds[index].add_field(name="Max", value=max_block, inline=True)

         print(embed_blocks)
         for _, embed in embeds.items():
            yield Response(embed=embed)

      @self._commandeer(name="pinall", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __pinall(ctx: aurflux.ty.GuildCommandCtx, _):
         """
         pinall
         ==
         Forces a re-check of all mapped channels for pins & permissions
         ==
         ==
         :param ctx:
         :param _:
         :return:
         """
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         chs_to_delete = []
         for from_ch_id, to_ch_id in configs["pinmap"].items():
            from_channel, to_channel = ctx.flux.get_channel(from_ch_id), ctx.flux.get_channel(to_ch_id)
            if not from_channel:
               chs_to_delete.append(from_ch_id)
               yield Response(f"Source channel with ID in config {from_ch_id} does not seem to exist anymore. Removing from config..")
               continue
            if not to_channel:
               chs_to_delete.append(from_ch_id)
               yield Response(f"Destination channel with ID in config {from_ch_id} does not seem to exist anymore. Removing from config..")
               continue

            if not isinstance(from_channel, discord.TextChannel):
               chs_to_delete.append(from_ch_id)
               yield Response(f"Source channel with ID in config {from_ch_id} does not seem to be a text channel. Removing from config..")
               continue
            if not isinstance(to_channel, discord.TextChannel):
               chs_to_delete.append(from_ch_id)
               yield Response(f"Destination channel with ID in config {from_ch_id} does not seem to be a text channel. Removing from config..")
               continue

            aurflux.utils.perm_check(from_channel, discord.Permissions(manage_messages=True, read_messages=True))
            aurflux.utils.perm_check(to_channel, discord.Permissions(embed_links=True, send_messages=True))

         async with ctx.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
            for ch_id in chs_to_delete:
               del cfg["pinmap"][ch_id]

         for channel_id in configs["pinmap"]:
            await self.router.submit(event=aurflux.FluxEvent(self.flux, "flux:guild_channel_pins_update", self.flux.get_channel(int(channel_id)), None))

         yield Response()

      # @self._commandeer(name="reverse", default_auths=[aurflux.auth.Record.allow_server_manager()])
      # async def __reverse(ctx: aurflux.ty.GuildCommandCtx, args: str):
      #    """
      #    reverse
      #    ==
      #    Toggles between oldest pin first (reverse = False) and newest pin first (reverse = True)
      #    ==
      #    ==
      #    :param ctx:
      #    :param args:
      #    :return:
      #    """
      #    async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg_w:
      #       cfg_w["reverse"] = not cfg_w["reverse"]
      #    return Response(f"Set reverse to {cfg_w['reverse']}")

      @self._commandeer(name="unmap", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __unmap(ctx: aurflux.ty.GuildCommandCtx, args: str):
         """
         unmap <source_channel>
         ==
         Deletes the map from <source_channel> to the destination
         ==
         <source_channel> : The source channel that has been mapped with `setup` before
         ==
         :param ctx:
         :return:
         """
         try:
            source_channel_r = aurflux.utils.find_mentions(args)[0]
         except (TypeError, IndexError):
            source_channel_r = int(args.strip())

         async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg_w:

            if source_channel_r not in cfg_w["pinmap"]:
               raise aurflux.errors.CommandError(f"`{source_channel_r}` not found in map: {', '.join(f'`{c}`' for c in cfg_w['pinmap'])}")
            del cfg_w["pinmap"][source_channel_r]
            try:
               del cfg_w["maxmap"][source_channel_r]
            except KeyError:
               pass

         desc = source_channel_r
         if (source_channel := await self.flux.get_channel_s(source_channel_r)):
            desc = source_channel.mention

         return Response(f"Removed {desc} from map.")

      @self._commandeer(name="import", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __import(ctx: aurflux.ty.GuildCommandCtx, _):
         """
         import
         ==
         Imports configs from Pinbot v1
         ==
         ==
         :param ctx:
         :param _:
         :return:
         """
         c = ctx.flux.get_channel(767823163823226931)
         assert isinstance(c, discord.TextChannel)

         await c.send(str(ctx.msg_ctx.guild.id))

         def message_check(ev: aurflux.FluxEvent) -> bool:
            message: discord.Message = ev.args[0]
            print(message)
            return message.channel == c and message.author.id == 535572077118488576

         async with ctx.msg_ctx.channel.typing():
            try:
               message = (await self.router.wait_for("flux:message", check=message_check, timeout=30)).args[0]
            except aio.TimeoutError as e:
               return Response("Timed out. Please try again later :(", status="error")
            warnings = ""
            async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
               maps, max_ = pickle.loads(base64.b85decode(message.content))
               logger.info(f"Importing for server {ctx.msg_ctx.guild}")
               logger.info(maps)
               logger.info(max_)
               for k, v in maps.items():
                  try:
                     await verify_channel_pair(k, v)
                  except ValueError as e:
                     warnings += f"The mapping <#{k}>[{k}] -> <#{v}>[{v}] contains invalid channel IDs, possibly deleted. Ignored\n"
                  except aurflux.errors.BotMissingPermissions as e:
                     warnings += f"Warning: {e}! These need to be added for this map to work.\n"
                  else:
                     cfg["pinmap"][k] = v
                     cfg["maxmap"][k] = max_

         return Response(f"Finished. Use `..maps` to see your imported settings.\n{warnings}")

      @self._commandeer(name="lb", default_auths=[aurflux.auth.Record.allow_server_manager()])
      async def __lb(ctx: aurflux.ty.GuildCommandCtx, args: str):
         """
         lb (<channel>)
         ==
         Tabulates a leaderboard of the top authors of pinned messages from a channel or the entire server
         ==
         channel: the channel (source or destination) to tabulate the leaderboard for. Leave blank for the entire server.
         ==
         :param ctx:
         :param _:
         :return:
         """
         try:
            channel = aurflux.utils.find_mentions(args)[0]
         except (TypeError, IndexError):
            channel = None

         configs = self.flux.CONFIG.of(ctx.msg_ctx)
