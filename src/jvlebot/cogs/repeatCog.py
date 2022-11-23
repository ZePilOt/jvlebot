from discord.ext import commands
from jvlebot import cfg
import logging

CONF = cfg.CONF
LOG = logging.getLogger('bot')


class Repeat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init = True

    @commands.command(pass_context=True)
    async def repeat(self, ctx, *, message):
        if ctx.message.author.id == 182381180941893632:
            channel = self.bot.get_channel(CONF.ANNONCE_CHANNEL_ID)
            await channel.send(message)


def setup(bot):
    bot.add_cog(Repeat(bot))
