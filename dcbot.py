import asyncio
import logging
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("creators_cafe_bot")

bot = commands.Bot(
    command_prefix=";",
    intents=intents,
    allowed_mentions=allowed_mentions
)


@bot.event
async def on_error(event_method, *args, **kwargs):
    logger.exception("Unhandled exception in event '%s'", event_method)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    command_name = ctx.command.qualified_name if ctx.command else "(unknown)"
    cog_name = ctx.cog.qualified_name if ctx.cog else "(no cog)"
    logger.error(
        "Command error: command=%s cog=%s user=%s channel=%s",
        command_name,
        cog_name,
        ctx.author,
        ctx.channel,
        exc_info=(type(error), error, error.__traceback__)
    )


async def main():
    if not TOKEN:
        raise ValueError("TOKEN is not set in .env")

    async with bot:
        for cog in COGS_EXTENSIONS:
            try:
                await bot.load_extension(cog)
                logger.info("Loaded extension: %s", cog)
            except Exception:
                logger.exception("Failed to load extension: %s", cog)
                raise
        await bot.start(TOKEN)

server_thread()
asyncio.run(main())
