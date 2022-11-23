#!/usr/bin/python

import argparse
import sys

import logging

from jvlebot import cfg
from jvlebot import log
from jvlebot import utils
from discord.ext.commands import Bot
import time
import discord

intents = discord.Intents(
    guilds=True,
    members=True,
    messages=True,
)


CONF = cfg.CONF

print(discord.__version__)
parser = argparse.ArgumentParser("Start the Discord bot")
parser.add_argument('--config-file', '-c', dest='config_file', default=f"config.py", help="Bot configuration file")
parser.add_argument('--log-dir', '-l', dest='log_dir', default=f"./logs/{utils.get_project_name()}/", help="Bot log folder")


def main():
    args = parser.parse_args()
    log.setup(args.log_dir, args.config_file)
    LOG = logging.getLogger('bot')
    CONF.load(args.config_file)

    sys.path.append(utils.get_project_name())

    bot = Bot(command_prefix=CONF.COMMAND_PREFIX, pm_help=True, intents=intents)

    LOG.info("bot config : " + args.config_file)

    for extension in CONF.LOADED_EXTENSIONS:
        try:
            extension_module_name = f"{utils.get_project_name()}.cogs"
            bot.load_extension(extension_module_name + "." + extension)
            LOG.info(f"The extension '{extension.split('.')[0]}' has been successfully loaded")
        except Exception as e:
            LOG.exception(f"Failed to load extension '{extension.split('.')[0]}'")
            LOG.error(e)

    while True:
        try:
            bot.loop.run_until_complete(bot.start(CONF.DISCORD_BOT_TOKEN))
        except Exception as e:
            LOG.error(e)
            time.sleep(600)


if __name__ == "__main__":
    main()
