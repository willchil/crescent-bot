from event_creator import create_event
from RecNetLogin.recnetlogin import RecNetLogin
import discord
from discord import app_commands
from dotenv import dotenv_values


CRESCENT_MEDIA = 1188116803814162522
BOT_TOKEN = dotenv_values(".env.secret")["BOT_TOKEN"]

# Initialize client
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Define an event handler for the ready event, sync commands with guild
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=CRESCENT_MEDIA))
    print(f"Logged in as {client.user}")

# Register RecNet event creation command
@tree.command(
    name="create-event",
    description="Create a ^CrescentNightclub event at 10:00PM PT on the upcoming Friday.",
    guild=discord.Object(id=CRESCENT_MEDIA)
)
async def create_event_command(interaction):
    rnl = RecNetLogin()
    token = rnl.get_token(include_bearer=True)
    result = await create_event(token)
    rnl.close()
    await interaction.response.send_message(result)

client.run(BOT_TOKEN)