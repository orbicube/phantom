import discord
from discord.ext import commands
from discord import app_commands

import aiosqlite
from datetime import datetime
from typing import Optional

class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    base_url = "https://api.willyweather.com.au/v2/R2Y5NmU2ZDljMTYzOGQ4YWUwMGMwZj/"
    headers = {
        "User-Agent": "WillyWeatherKit/2.9.11",
    }

    async def get_weather(self, ctx, postcode: Optional[str]):

        if not postcode:
            async with aiosqlite.connect("ext/data/weather.db") as db:
                async with db.execute(""" SELECT postcode FROM weather
                    WHERE disc_user=?""", (ctx.message.author.id,)) as cursor:
                    postcode = await cursor.fetchone()

            if not postcode:
                await ctx.reply(("No postcode found. "
                    "Please retry with your postcode."), ephemeral=True)
                return

            postcode = postcode[0]

        params = {
            "query": postcode
        }
        r = await self.bot.http_client.get(
            f"{self.base_url}search.json",
            params=params)
        search = r.json()

        if not search:
            await ctx.reply(f"No results found for {postcode}.",
                ephemeral=True)
            return

        loc_name = f"{search[0]['name']}, {search[0]['state']}"
        loc_url = f"{self.base_url}locations/{search[0]['id']}/weather.json"

        async with aiosqlite.connect("ext/data/weather.db") as db:
            await db.execute("REPLACE INTO weather VALUES (?, ?)",
                (ctx.message.author.id, postcode))
            await db.commit()

        return loc_name, loc_url

    @app_commands.describe(postcode="AU postcode, will be saved for subsequent uses")
    @commands.hybrid_command()
    async def wz(self, ctx, postcode: Optional[str]):
        """ Get current weather for a given Australian postcode """

        loc_name, loc_url = await self.get_weather(ctx, postcode)

        params = {
            "observational": "true",
            "forecasts": "weather",
            "days": "1"
        }
        r = await self.bot.http_client.get(
            loc_url, headers=self.headers, params=params)
        weather = r.json()

        obs = weather["observational"]["observations"]
        current = obs["temperature"]["temperature"]
        humidity = obs["humidity"]["percentage"]

        wind = obs["wind"]["speed"]
        wind_direction = obs["wind"]["directionText"]
        gust = obs["wind"]["gustSpeed"]

        forecast = weather["forecasts"]["weather"]["days"][0]["entries"][0]
        sky = forecast["precis"].replace('.',',')
        high = forecast["max"]
        low = forecast["min"]

        if gust and gust != wind:
            gustcheck = f", gusting at {gust}km/h"
        else:
            gustcheck = ""

        await ctx.reply((
            f"**{loc_name}**\n{sky}\nCurrently **{current}**°C. "
            f"High of {high}°C, low of {low}°C.\n"
            f"Wind is {wind}km/h{gustcheck}. Humidity of {humidity}%."))


    @app_commands.describe(postcode="AU postcode, will be saved for subsequent uses")
    @commands.hybrid_command()
    async def fc(self, ctx, postcode: Optional[str]):
        """ Get forecast for a given Australian postcode """

        loc_name, loc_url = await self.get_weather(ctx, postcode)

        params = {
            "forecasts": "weather,temperature",
            "days": "7"
        }
        r = await self.bot.http_client.get(
            loc_url, headers=self.headers, params=params)
        weather = r.json()

        forecast = weather["forecasts"]["weather"]["days"]

        msg = f"Forecast for **{loc_name}**\n"

        for day in forecast:
            time_obj = datetime.strptime(day["dateTime"], "%Y-%m-%d %X")
            day_name = time_obj.strftime("%a")

            data = day["entries"][0]
            sky = data["precis"]
            if ". " in sky:
                sky = sky.split(". ")[1]

            msg += f"**{day_name}** {sky}, {data['min']}°C - {data['max']}°C\n"

        await ctx.reply(msg)


async def setup(bot):
    async with aiosqlite.connect("ext/data/weather.db") as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS weather
            (disc_user integer, postcode text, UNIQUE(disc_user))""")
        await db.commit()

    await bot.add_cog(Weather(bot))