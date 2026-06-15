import discord
import pickledb
from server_constants import *
from discord.ext import commands


# Initialize client
intents = discord.Intents.default()
bot = commands.Bot(intents=intents, command_prefix="/")

# Runs once inside the bot's event loop, before on_ready. Initializing the
# pickledb instance here (rather than at import time) binds its internal
# asyncio.Lock to the bot's running loop, so awaited get/set calls work.
@bot.event
async def setup_hook():
    bot.user_data = pickledb.PickleDB('user_data.db')
    await bot.user_data.load()
    await bot.load_extension('admin')
    # await bot.load_extension('event')
    await bot.load_extension('register')
    await bot.load_extension('update_group_roles_cog')
    await bot.tree.sync(guild=discord.Object(id=CRESCENT_MEDIA))

# Define an event handler for the ready event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


bot_token = DOTENV["BOT_TOKEN"]
bot.run(bot_token)