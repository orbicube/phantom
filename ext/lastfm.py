import discord
from discord.ext import commands
from discord import app_commands

from typing import Optional
import aiosqlite

from credentials import LASTFM_KEY

class LastFM(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.describe(username="last.fm username, will be saved for subsequent uses")
    @app_commands.command()
    async def np(self, ctx, username: Optional[str]):
        """ Post currently playing track info from last.fm """

        if not username:
            async with aiosqlite.connect("ext/data/lastfm.db") as db:
                async with db.execute("""SELECT lfm_user FROM lastfm
                    WHERE disc_user=?""", (ctx.message.author.id,)) as cursor:
                    username = await cursor.fetchone()

            if not username:
                await ctx.reply(("No last.fm username found. "
                    "Please retry with your last.fm username."))
                return

            username = username[0]
        
        recent_params = {
            "api_key": LASTFM_KEY,
            "format": "json",
            "method": "user.getrecenttracks",
            "user": username
        }
        r = await self.bot.http_client.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=recent_params)
        tracks_json = r.json()

        # Check for error message
        try:
            await ctx.reply(tracks_json["message"], ephemeral=True)
            return
        except:
            pass

        # Grab latest track, catch error if no tracks
        try:
            track = tracks_json["recenttracks"]["track"][0]
        except:
            await ctx.reply("{username} hasn't scrobbled anything yet.",
                ephemeral=True)

        # Check if they're currently listening to a track
        try:
            if track["@attr"]["nowplaying"]:
                live_msg = "is now listening"
        except:
            live_msg = "last listened"

        # Get extra track info
        info_params = {
            "api_key": LASTFM_KEY,
            "format": "json",
            "method": "track.getinfo",
            "track": track["name"],
            "artist": track["artist"]["#text"],
            "username": username
        }
        r = await self.bot.http_client.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=info_params)
        track_info = r.json()

        img = next(item for item in track["image"]
            if item["size"] == "extralarge")
        img = img["#text"]

        embed = discord.Embed(
            title=track["name"],
            description=track["artist"]["#text"],
            url=track["url"],
            color=12124160)

        embed.set_author(
            name = f"{username} {live_msg} to",
            icon_url = "https://ptpimg.me/wr9707.png",
            url = f"https://www.last.fm/user/{username}")

        if img:
            embed.set_thumbnail(url=img)

        if track["album"]["#text"]:
            embed.set_footer(text=track["album"]["#text"])

        await ctx.reply(embed=embed)

        async with aiosqlite.connect("ext/data/lastfm.db") as db:
            await db.execute("REPLACE INTO lastfm VALUES (?, ?)",
                (ctx.message.author.id, username))
            await db.commit()


async def setup(bot):
    async with aiosqlite.connect("ext/data/lastfm.db") as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS lastfm
            (disc_user integer, lfm_user text, UNIQUE(disc_user))""")
        await db.commit()

    await bot.add_cog(LastFM(bot))


