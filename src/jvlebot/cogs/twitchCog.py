
import discord
from discord.ext import commands
from discord.ext import tasks
from twitchAPI.twitch import Twitch

from jvlebot import cfg
import logging

import string
import random

CONF = cfg.CONF
LOG = logging.getLogger('bot')


class Channel():
    def __init__(self, name, url, channelid, description, profile):
        self.uid = channelid
        self.name = name
        self.url = url
        self.online = False
        self.description = description
        self.profile_url = profile


class TwitchBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init = True
        self.twitch = Twitch(CONF.TWITCH_API_KEY, CONF.TWITCH_APP_SECRET)
        self.discord_channel = None
        self.channels = []
        for twitch_chan_id in CONF.TWITCH_CHANNELS:
            LOG.debug("Adding channel " + str(twitch_chan_id))
            infos = self.twitch.get_users(user_ids=str(twitch_chan_id))
            url = "https://www.twitch.tv/" + infos["data"][0]["login"]
            self.channels.append(Channel(infos["data"][0]["display_name"], url, twitch_chan_id, infos["data"][0]["description"], infos["data"][0]["profile_image_url"]))

        self.check_twitch.start()

    @commands.Cog.listener()
    async def on_ready(self):
        self.discord_channel = self.bot.get_channel(CONF.ANNONCE_CHANNEL_TWITCH_ID)

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def check_twitch(self):
        try:
            for channel in self.channels:

                channel_id = channel.uid
                stream = self.twitch.get_streams(user_id=str(channel_id))
                if len(stream["data"]) == 0:
                    channel.online = False
                else:
                    if channel.online is False:
                        stream_game = stream["data"][0]["game_name"]
                        stream_url = channel.url
                        stream_name = channel.name
                        stream_title = stream["data"][0]["title"]
                        discord_message = ""
                        if "factor" in stream_name.lower():
                            discord_message = "Mes créateurs, les gens de Factornews, sont maintenant live sur {} ! @here".format(stream_game)
                        else:
                            discord_message = "{} est maintenant live sur {} ! @here".format(stream_name, stream_game)
                        stream_description = channel.description

                        stream_preview = stream["data"][0]["thumbnail_url"]
                        stream_preview = stream_preview.replace("{width}", "640")
                        stream_preview = stream_preview.replace("{height}", "320")
                        rnd = random.sample(string.ascii_letters, 6)
                        rnd_str = "".join(rnd)
                        stream_preview = stream_preview.replace('./', '')
                        stream_preview = stream_preview.replace('./', '') + "?rnd=" + rnd_str
                        stream_logo = channel.profile_url
                        stream_logo = stream_logo.replace('./', '')

                        embed = discord.Embed(title=stream_title, description=stream_description, url=stream_url, color=0x6441a4)
                        embed.add_field(name="started at", value=stream["data"][0]["started_at"])
#                       embed.add_field(name="Views", value=stream["channel"]["views"])
                        embed.set_thumbnail(url=stream_logo)
                        embed.set_image(url=stream_preview)
                        await self.discord_channel.send(discord_message, embed=embed)
                        channel.online = True
        except Exception as e:
            LOG.error(e)

    @check_twitch.before_loop
    async def before_my_task(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in


def setup(bot):
    bot.add_cog(TwitchBot(bot))
