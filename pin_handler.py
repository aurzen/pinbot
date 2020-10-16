from __future__ import annotations

import typing as ty
import aurflux
import discord
import itertools as itt
import collections as clc
import asyncio as aio
import aurcore as aur

if ty.TYPE_CHECKING:
   import datetime

VIDEO_EXTS = ["3g2", "3gp", "aaf", "asf", "avchd", "avi", "drc", "flv", "m2v", "m4p", "m4v", "mkv", "mng", "mov", "mp2", "mp4", "mpe", "mpeg", "mpg", "mpv", "mxf", "nsv", "ogg",
              "ogv", "qt", "rm", "rmvb", "roq", "svi", "vob", "webm", "wmv", "yuv"]
IMAGE_EXTS = ["ase", "art", "bmp", "blp", "cd5", "cit", "cpt", "cr2", "cut", "dds", "dib", "djvu", "egt", "exif", "gif", "gpl", "grf", "icns", "ico", "iff", "jng", "jpeg", "jpg",
              "jfif", "jp2", "jps", "lbm", "max", "miff", "mng", "msp", "nitf", "ota", "pbm", "pc1", "pc2", "pc3", "pcf", "pcx", "pdn", "pgm", "PI1", "PI2", "PI3", "pict", "pct",
              "pnm", "pns", "ppm", "psb", "psd", "pdd", "psp", "px", "pxm", "pxr", "qfx", "raw", "rle", "sct", "sgi", "rgb", "int", "bw", "tga", "tiff", "tif", "vtf", "xbm", "xcf",
              "xpm", "3dv", "amf", "ai", "awg", "cgm", "cdr", "cmx", "dxf", "e2d", "egt", "eps", "fs", "gbr", "odg", "svg", "stl", "vrml", "x3d", "sxd", "v2d", "vnd", "wmf", "emf",
              "art", "xar", "png", "webp", "jxr", "hdp", "wdp", "cur", "ecw", "iff", "lbm", "liff", "nrrd", "pam", "pcx", "pgf", "sgi", "rgb", "rgba", "bw", "int", "inta", "sid",
              "ras", "sun", "tga"]


def message2embed(message: discord.Message, embed_color: discord.Color = None):
   embeds = []

   for m, embed in itt.zip_longest([message], [*message.embeds, *message.attachments], fillvalue=None):

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
         if any(embed.url.endswith(ext) for ext in IMAGE_EXTS):
            new_embed.set_image(url=embed.url)
         else:
            new_embed.description = (new_embed.description or "") + f"\n{embed.url}"
      if isinstance(embed, discord.Embed) and embed.url:
         if embed.thumbnail:
            new_embed.set_image(url=embed.thumbnail.url)
         else:
            new_embed.set_image(url=embed.url)

      new_embed.description = (str(new_embed.description) if new_embed.description != discord.Embed.Empty else "") + f"\n\n[Jump to message]({message.jump_url})"
      print(new_embed.to_dict())

      embeds.append(new_embed)

   return embeds


class PinHandler(aurflux.FluxCog):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.locks: ty.Dict[str, aio.Lock] = clc.defaultdict(aio.Lock)

   def load(self):
      @self.router.listen_for("flux:guild_channel_pins_update")
      @aur.Eventful.decompose
      async def message_update_handler(channel: discord.TextChannel, last_pin: datetime.datetime):
         g_ctx = aurflux.context.ManualGuildCtx(flux=self.flux, guild=channel.guild)

         async with self.locks[channel.id]:
            if channel.id not in (config := self.flux.CONFIG.of(g_ctx))["pinmap"]:
               return
            pins: ty.List[discord.Message] = sorted(await channel.pins(), key=lambda x: x.created_at)
            num_to_unpin = max(0, len(pins) - config["maxmap"][channel.id])
            for pin in pins[:num_to_unpin]:
               for embed in message2embed(pin):
                  await self.flux.get_channel(config["pinmap"][channel.id]).send(
                     embed=embed
                  )
               await pin.unpin()
         try:
            del self.locks[channel.id]
         except KeyError:
            pass
