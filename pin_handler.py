from __future__ import annotations

import typing as ty
import aurflux
import discord
import itertools as itt
import collections as clc
import asyncio as aio

if ty.TYPE_CHECKING:
   import datetime


def message2embed(message: discord.Message, embed_color: discord.Color = None):
   embeds = []
   # for image in message.
   print("Converting!@")
   print(len(message.embeds))
   print(len(message.attachments))
   for m, embed in itt.zip_longest([message], [*message.embeds, *message.attachments], fillvalue=None):
      print("New embed!")
      print(m)
      print(embed)
      new_embed = discord.Embed()
      if isinstance(embed, discord.Embed) and (embed.title or embed.description):
         new_embed = embed
         new_embed.description = (str(new_embed.description) if new_embed.description != discord.Embed.Empty else "") + f"\n\n[Jump to message]({message.jump_url})"
         embeds.append(new_embed)
         continue

      if m:
         new_embed.timestamp = m.created_at

         new_embed.set_author(name=m.author.name, icon_url=m.author.avatar_url, url=m.jump_url)
         new_embed.description = f"{m.content[:1900] + ('...' if len(m.content) > 1900 else '')}"
         new_embed.set_footer(text=f"#{m.channel.name} | Sent at {m.created_at.isoformat('@').replace('@', ' at ')[:-7]}")
      if isinstance(embed, discord.Attachment):
         new_embed.set_image(url=embed.url)
      if isinstance(embed, discord.Embed) and embed.url:
         if embed.thumbnail:
            new_embed.set_image(url=embed.thumbnail.url)
         else:
            new_embed.set_image(url=embed.url)
         #
         # if embed is not None and embed.url:
         #     print("image!")
         #     print(embed.url
         #     new_embed.set_image(url=embed.url)
         # elif embed is not None and (embed.title or embed.description):
         #     new_embed = embed
         #
      # if new_embed.description:
      new_embed.description = (str(new_embed.description) if new_embed.description != discord.Embed.Empty else "") + f"\n\n[Jump to message]({message.jump_url})"
      print(new_embed.to_dict())
      print("_----------")

      embeds.append(new_embed)

   #
   # for embed in message.embeds:
   #     print(embed.to_dict())
   #     if embed.description or embed.title:
   #         embed.description = f"{embed.description}\n\n[Jump to message]({message.jump_url})"
   #         embeds.append(embed)
   #     else:
   #         new_embed = discord.Embed(
   #             timestamp=message.created_at
   #         )
   #         new_embed.set_author(name=message.author.name, icon_url=message.author.avatar_url, url=message.jump_url)
   #
   #         new_embed.description = f"{message.content[:1900] + ('...' if len(message.content) > 1900 else '')}\n\n[Jump to message]({message.jump_url})"
   #         new_embed.set_footer(text=f"#{message.channel.name} | Sent at {message.created_at.isoformat('@').replace('@', ' at ')[:-7]}")
   #         if embed.url:
   #             new_embed.set_image(url=embed.url)
   #         new_embed.description = f"{embed.description}\n\n[Jump to message]({message.jump_url})"
   #         embeds.append(embed)
   #
   # for attachment in message.attachments:
   #     new_embed = discord.Embed(
   #         timestamp=message.created_at
   #     )
   #     new_embed.set_author(name=message.author.name, icon_url=message.author.avatar_url, url=message.jump_url)
   #
   #     # new_embed.description = f"{message.content[:1900] + ('...' if len(message.content) > 1900 else '')}\n\n[Jump to message]({message.jump_url})"
   #     new_embed.set_footer(text=f"#{message.channel.name} | Sent at {message.created_at.isoformat('@').replace('@', ' at ')[:-7]}")
   #     new_embed.set_image(url=attachment.url)
   #     new_embed.description = f"[Jump to message]({message.jump_url})"
   #     embeds.append(new_embed)
   # print(embeds)
   return embeds
   # return [new_embed, *message.embeds]
   # if message.embeds:
   #     for m_embed in message.embeds:
   #         extra_embed = discord.Embed()
   #         if m_embed.url:
   #             extra_embed.set_image(url=m_embed.url)
   #         if m_embed.image:
   #             extra_embed.set_image(url=m_embed.image.url)
   #         if m_embed.video:
   #             extra_embed._video = m_embed._video
   #
   #         break
   # if message.attachments:
   #     for attachment in message.attachments:
   #         if attachment.url:
   #             new_embed.set_image(url=attachment.url)
   #             break
   # if embed_color:
   #     new_embed.colour = embed_color


class PinHandler(aurflux.AurfluxCog):
   listening_channels = set()

   def __init__(self, aurflux: aurflux.Aurflux):
      super().__init__(aurflux)
      self.locks: ty.Dict[str, aio.Lock] = clc.defaultdict(aio.Lock)

   def route(self):
      @self.router.endpoint("aurflux:guild_channel_pins_update", decompose=True)
      async def message_update_handler(channel: discord.TextChannel, last_pin: datetime.datetime):
         print("updating!")
         print( self.aurflux.CONFIG.of(channel.guild.id)["pinmap"])
         async with self.locks[channel.id]:
            if channel.id not in (config := self.aurflux.CONFIG.of(channel.guild.id))["pinmap"]:
               return
            print("!")
            pins: ty.List[discord.Message] = sorted(await channel.pins(), key=lambda x: x.created_at)
            print(f"{len(pins)} in {channel}")
            num_to_unpin = max(0, len(pins) - config["maxmap"][channel.id])
            print(num_to_unpin)
            for pin in pins[:num_to_unpin]:
               for embed in message2embed(pin):
                  await self.aurflux.get_channel(config["pinmap"][channel.id]).send(
                     embed=embed
                  )
               await pin.unpin()
         del self.locks[channel.id]
