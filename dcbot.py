import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from server import server_thread

load_dotenv()

TOKEN = os.getenv("TOKEN")

COGS_EXTENSIONS = [
    "cogs.analyze",
    "cogs.server_log",
    "cogs.voice_log",
    "cogs.voice_notify",
    "cogs.spam_guard"
]

intents = discord.Intents.all()
allowed_mentions = discord.AllowedMentions(roles=True)

bot = commands.Bot(
    command_prefix=";",
    intents=intents,
    allowed_mentions=allowed_mentions
)


async def main():
    async with bot:
        for cog in COGS_EXTENSIONS:
            await bot.load_extension(cog)
        await bot.start(TOKEN)

server_thread()
asyncio.run(main())
