import discord
from discord.ext import commands
from discord.ext import tasks
import sqlite3
import re
from jvlebot import cfg
import logging
import datetime
from discord import option
import matplotlib.pyplot as plt
import pandas as pd
import itertools
import io

CONF = cfg.CONF
LOG = logging.getLogger('bot')

# If modifying these scopes, delete the file token.json.


class Stats(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.readableChannels = []
        self.users = {}
        self.users_words = {}
        self.users_sentences = {}
        self.update_db.start()
        self.server = None

    @commands.Cog.listener()
    async def on_ready(self):

        conn = sqlite3.connect('stats.db')
        c = conn.cursor()
        c.execute("SELECT last_users_stats FROM last_track")

        for server in self.bot.guilds:
            member = server.get_member(self.bot.user.id)
            self.server = server
            break

        for chan in self.bot.get_all_channels():
            if type(chan) == discord.channel.TextChannel:
                perms = chan.permissions_for(member)
                if perms.read_message_history and perms.read_messages:
                    self.readableChannels.append(chan)
                    print("adding ", chan)

    @tasks.loop(seconds=60 * 60 * 12)  # task runs every 60 seconds * 60 minutes * 12 hours
    async def update_db(self):
        conn = sqlite3.connect('stats.db')
        c = conn.cursor()
        c.execute("SELECT last_users_stats FROM last_track")
        selected = c.fetchone()
        c.close()
        lastTrack = selected[0]
        beforeDate = datetime.datetime.now()
        afterDate = datetime.datetime.strptime(lastTrack, "%Y-%m-%d %H:%M:%S.%f")
        allEmojis = {}

        for chan in self.readableChannels:
            print("scanning", chan)
            async for message in chan.history(limit=None, after=afterDate, before=beforeDate, oldest_first=True):
                args = (str(message.author.id), message.content, message.channel.name, message.created_at)
                c = conn.cursor()
                c.execute("INSERT INTO talks VALUES (?,?, ?, ?)", args)
                for reaction in message.reactions:
                    emojiStr = None
                    if type(reaction.emoji) == str:
                        emojiStr = reaction.emoji
                    else:
                        emojiStr = reaction.emoji.name
                    if emojiStr not in allEmojis:
                            allEmojis[emojiStr] = {}

                    users = await reaction.users().flatten()
                    for user in users:
                        if user.id not in allEmojis[emojiStr]:
                            allEmojis[emojiStr][user.id] = 0
                        allEmojis[emojiStr][user.id] = allEmojis[emojiStr][user.id] + 1
                c.close()
            conn.commit()

        for emoji in allEmojis:
            for user in allEmojis[emoji]:
                args = (emoji, int(user),)
                c = conn.cursor()
                c.execute("SELECT counter FROM reactions WHERE emoji == ? and user_id == ?", args)
                selected = c.fetchone()
                if selected is not None:
                    counter = selected[0]
                    args = (int(allEmojis[emoji][user]) + counter, emoji, int(user),)
                    c.execute("UPDATE reactions SET counter = ? WHERE emoji == ? and user_id == ?", args)

                else:
                    args = (emoji, int(user), int(allEmojis[emoji][user]))
                    c.execute("INSERT INTO reactions VALUES (?, ?, ?)", args)
                c.close()

            conn.commit()

        conn.commit()

        c = conn.cursor()
        args = (str(beforeDate),)
        c.execute("UPDATE last_track SET last_users_stats = ? WHERE id = 1;", args)
        c.close()
        conn.commit()
        conn.close()

    @update_db.before_loop
    async def before_my_task(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in

    @commands.slash_command(guild_ids=[438626370180874240], name="compare", description="compare le pourcentage d'utilisation de ces mots")
    @option("mots", description="Liste des mots à comparer")
    async def compare(self, ctx, mots: str):
        regexp = re.compile(r"('.*?'|\".*?\"|\S+)")
        words = re.findall(regexp, mots)
        conn = sqlite3.connect('stats.db')
        c = conn.cursor()
        sizes = []
        await ctx.respond(ctx.author.name + " a demandé de comparer : " + " ".join(words))

        for word in words:
            args = ("\"" + word + "\"*",)
            c.execute("SELECT COUNT(*) FROM talks WHERE message MATCH ?", args)
            selected = c.fetchone()
            sizes.append(selected[0])

        explode = [0.1] * len(words)
        fig1, ax1 = plt.subplots()
        ax1.pie(sizes, explode=explode, labels=words, autopct='%1.1f%%', shadow=True, startangle=90)

        resultsTitle = []
        for i in range(len(words)):
            resultsTitle.append(words[i] + " (" + str(sizes[i]) + ")")

        title = " vs ".join(resultsTitle)
        buf = io.BytesIO()
        plt.savefig(buf, format='jpg')
        buf.seek(0)
        image_file = discord.File(buf, filename=f"stat_compare.jpg")
        await ctx.respond(title, file=image_file)
        buf.close()
        conn.close()

    @commands.slash_command(pass_context=True, name="topreact", description="le top 5 des personnes ayant le plus utilisé cet emoji en réaction")
    @option("mots", description="emoji à chercher")
    async def topreaction(self, ctx, emoji: str):
        conn = sqlite3.connect('stats.db')
        await ctx.respond(ctx.author.name + " a demandé le top des réactions utilisant ***" + emoji + "***")
        emojiToSearch = emoji
        if emoji.startswith("<"):
            regexp = "<:(\\w+):\\d+>"
            words = re.findall(regexp, emoji)
            emojiToSearch = words[0]

        c = conn.cursor()
        args = (emojiToSearch,)

        c.execute("SELECT user_id, counter FROM reactions WHERE emoji == ? ORDER by 2 DESC LIMIT 5", args)
        selected = c.fetchall()
        result = "Top " + str(len(selected)) + " pour ***" + emoji + "*** utilisé en réaction\n"
        rank = 1
        for r in selected:
            author = self.server.get_member(int(r[0]))
            count = r[1]
            if author:
                result = result + str(rank) + ". " + author.name + " (" + str(count) + ")\n"
            else:
                result = result + str(rank) + ". " + "<@" + str(r[0]) + ">" + " (" + str(count) + ")\n"
            rank = rank + 1
        conn.close()
        await ctx.respond(result)

    @commands.slash_command(pass_context=True, name="top", description="le top 5 des personnes ayant le plus utilisé ce mot")
    @option("mots", description="mot à chercher")
    async def top(self, ctx, mot: str):
        conn = sqlite3.connect('stats.db')
        c = conn.cursor()
        args = ("\"" + mot + "\"*",)
        await ctx.respond(ctx.author.name + " a demandé le top pour ***" + mot + "***")
        c.execute("SELECT user_id, count(user_id) FROM talks WHERE message MATCH ? GROUP BY user_id ORDER by 2 DESC LIMIT 5", args)
        selected = c.fetchall()
        result = "Top " + str(len(selected)) + " pour ***" + mot + "***\n"
        rank = 1
        for r in selected:
            author = self.server.get_member(int(r[0]))
            count = r[1]
            if author:
                result = result + str(rank) + ". " + author.name + " (" + str(count) + ")\n"
            else:
                result = result + str(rank) + ". " + "<@" + r[0] + ">" + " (" + str(count) + ")\n"
            rank = rank + 1
        conn.close()
        await ctx.respond(result)

    @commands.slash_command(pass_context=True, name="montop50", description="Vos 50 mots de plus de 6 lettres les plus utilisés")
    async def montop50(self, ctx):

        await ctx.respond("Les 50 mots les plus utilisés par " + ctx.author.name)
        conn = sqlite3.connect('stats.db')
        c = conn.cursor()
        member = ctx.author
        args = (str(member.id),)
        c.execute("SELECT message FROM talks WHERE user_id MATCH ?", args)
        results = c.fetchall()

        regexp = re.compile(r"\b([a-zA-Z\u00C0-\u00FF]{6,})\b")

        top = {}
        for line in results:
            message = line[0]

            words = re.findall(regexp, message)

            for word in words:
                word = word.lower()
                if word not in top:
                    top[word] = 0
                top[word] = top[word] + 1

        conn.close()

        top = {k: v for k, v in sorted(top.items(), reverse=True, key=lambda item: item[1])}
        top50 = list(itertools.islice(top, 50))
        topResult = []
        for word in top50:
            topResult.append("***" + word + "*** (" + str(top[word]) + ")")
        results = " - ".join(topResult)
        await ctx.respond(results)

    @commands.slash_command(pass_context=True, name="trend", description="la popularité d'un mot à travers les âges")
    @option("mots", description="Liste des mots à comparer")
    async def trend(self, ctx, mots: str):
        conn = sqlite3.connect('stats.db')
        c = conn.cursor()

        regexp = re.compile(r"('.*?'|\".*?\"|\S+)")
        words = re.findall(regexp, mots)

        words = words[:4]

        await ctx.respond(ctx.author.name + "a demandé les tendances pour " + " vs ".join(words))

        datas = []

        for word in words:
            words_results = []
            args = ("\"" + word + "\"*",)
            c.execute("SELECT * FROM talks WHERE message MATCH ?", args)
            selected = c.fetchall()

            for r in selected:
                # author = r[0]
                # message = r[1]
                # salon = r[2]
                date_str = r[3][0:10]
                datetime_object = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                words_results.append(datetime_object)

            df = pd.DataFrame({word: words_results})
            data = df.groupby([word])[word].size()
            datas.append(data)

        df = pd.concat(datas, axis=1)

        for word in words:
            df[word] = df[word].fillna(0)

        mindate = df.index.min()
        maxdate = df.index.max()

        dr = pd.date_range(start=mindate, end=maxdate, freq='M')
        dpi = 72
        # Create figure and plot space
        _ = plt.figure(figsize=(2000 / dpi, 500 / dpi))

        dr = pd.date_range(start=mindate, end=maxdate, freq='M')

        for word in words:
            plt.bar(df.index.values, df[word], label=word, width=.5)
            plt.ylabel("Occurences")
            plt.legend()
            plt.xticks(rotation=45)
            plt.xticks(dr)

        plt.xlabel("Date")

        title = " vs ".join(words)
        buf = io.BytesIO()
        plt.savefig(buf, format='jpg')
        buf.seek(0)
        image_file = discord.File(buf, filename=f"stat_trend.jpg")
        await ctx.respond(title, file=image_file)
        buf.close()
        conn.close()


def setup(bot):
    bot.add_cog(Stats(bot))
