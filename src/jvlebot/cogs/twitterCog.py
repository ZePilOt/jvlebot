
import discord
from discord.ext import commands
from discord.ext import tasks

from tweepy import OAuthHandler
from tweepy import API
from tweepy import Cursor
from jvlebot import cfg
import logging

import sqlite3


CONF = cfg.CONF
LOG = logging.getLogger('bot')


class Twitter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        auth = OAuthHandler(CONF.TWITTER_CONSUMER_KEY, CONF.TWITTER_CONSUMER_SECRET)
        auth.set_access_token(CONF.TWITTER_ACCESS_TOKEN, CONF.TWITTER_ACCESS_TOKEN_SECRET)
        self.auth_api = API(auth)

        self.mostRecents = {}
        self.channel = None
        conn = sqlite3.connect('twitter.db')
        c = conn.cursor()

        c.execute("SELECT * FROM twitter")
        results = c.fetchall()

        if len(results) == 0:
            conn.close()
            return

        for result in results:
            LOG.info("Adding twitter user " + result[0])
            self.mostRecents[result[0]] = result[1]

        conn.close()

        self.check_twitter.start()

    @commands.Cog.listener()
    async def on_ready(self):
        self.channel = self.bot.get_channel(CONF.ANNONCE_CHANNEL_ID)

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def check_twitter(self):
        for target in self.mostRecents:
            try:
                LOG.debug("checking account " + target)
                tweets = Cursor(self.auth_api.user_timeline, screen_name=target, since_id=self.mostRecents[target], tweet_mode="extended")
                for status in tweets.items():
                    if status.in_reply_to_status_id is None and hasattr(status, "retweeted_status") is False:
                        link = "https://twitter.com/{}/status/{}".format(target, status.id_str)
                        if status.full_text.startswith("@"):
                            continue

                        embed = discord.Embed(title=target, description=status.full_text, url=link, color=0x1DA1F2)
                        if "media" in status.entities:
                            for media in status.entities["media"]:
                                embed.set_image(url=media["media_url"])
                                break

                        embed.set_thumbnail(url=status.user.profile_image_url)
                        embed.set_footer(text=status.created_at)
                        LOG.debug("Posting tweet")
                        await self.channel.send(embed=embed)

                    if status.id > self.mostRecents[target]:
                        self.mostRecents[target] = status.id
                        conn = sqlite3.connect('twitter.db')
                        c = conn.cursor()
                        args = (status.id, target)
                        c.execute("UPDATE twitter SET lastTweet = ? WHERE account = ?", args)
                        conn.commit()
                        conn.close()
            except Exception as e:
                LOG.error(e)

    @check_twitter.before_loop
    async def before_my_task(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in


def setup(bot):
    bot.add_cog(Twitter(bot))
