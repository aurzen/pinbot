from __future__ import annotations

import typing as ty
import aurflux

if ty.TYPE_CHECKING:
    import discord
    import datetime

def message2embed(message: discord.Message, embed_color: discord.Color = None):
    embeds = []
    main_embed = discord.Embed(
        timestamp=message.created_at
    )
    main_embed.set_author(name=message.author.name, icon_url=message.author.avatar_url, url=message.jump_url)

    main_embed.description = f"{message.content[:1900] + '...' if len(message.content > 1900) else ''}\n\n[Jump to message]({message.jump_url})"
    main_embed.set_footer(text=f"#{message.channel.name} | Sent at {message.created_at.isoformat('@').replace('@',' at ')[:-7]}")


    return  [main_embed, *message.embeds]
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
    #             main_embed.set_image(url=attachment.url)
    #             break
    # if embed_color:
    #     main_embed.colour = embed_color

class PinHandler(aurflux.AurfluxCog):
    listening_channels = set()
    def __init__(self, aurflux: aurflux.Aurflux):
        super().__init__(aurflux)

    def route(self):
        @self.router.endpoint("aurflux:guild_channel_pins_update", decompose=True)
        async def message_update_handler(channel: discord.TextChannel, last_pin: datetime.datetime):
            if channel.id not in self.listening_channels:
                return
            pins : ty.List[discord.Message] = sorted(await channel.pins(), key = lambda x: x.created_at, reverse=True)
            if (config := self.aurflux.CONFIG.of(channel.guild.id)) and channel.guild.id in config["pinmap"]:
                for pin in pins[:len(pins) - config["maxmap"][channel.guild.id]]:
                    await self.aurflux.get_channel(config["pinmap"][channel.guild.id]).send(
                        embeds=message2embed(pin)
                    )