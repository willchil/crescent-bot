import discord
import pickledb
from server_constants import *
from discord.ext import commands


# Initialize client
intents = discord.Intents.default()
bot = commands.Bot(intents=intents, command_prefix="/")

# Define an event handler for the ready event, sync commands with guild
@bot.event
async def on_ready():
    bot.user_data = await pickledb.PickleDB('user_data.db').load()
    await bot.load_extension('admin')
    # await bot.load_extension('event')
    await bot.load_extension('register')
    await bot.load_extension('update_group_roles_cog')
    await bot.tree.sync(guild=discord.Object(id=CRESCENT_MEDIA))
    print(f"Logged in as {bot.user}")


bot_token = DOTENV["BOT_TOKEN"]
bot.run(bot_token)