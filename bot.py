import discord
import pytz
from event_creator import create_event
from RecNetLogin.recnetlogin import RecNetLogin
from discord import app_commands
from datetime import datetime, timedelta
from dotenv import dotenv_values


CRESCENT_MEDIA = 1188116803814162522
EVENT_ROLE = 1188332286500933713
OWNER_ROLE = 1188119778611712040
BOT_CHANNEL = 1194502014244225164
EVENTS_CHANNEL = BOT_CHANNEL #1188119118747013210 # Redirecting while testing

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
    (start_time, end_time) = get_event_times()
    result = await create_event(token, start_time, end_time)
    if result[0]:
        channel = client.get_channel(EVENTS_CHANNEL)
        formatted_time = f"<t:{int(datetime.timestamp(start_time))}:f>"
        message = await channel.send(f"<@&{EVENT_ROLE}> Crescent Nightclub will be hosting an event at {formatted_time}! RSVP and invite your friends below!\n\n{result[1]}")
        await interaction.response.send_message(f"Event created. {message.jump_url}")
    else:
        channel = client.get_channel(BOT_CHANNEL)
        message = await channel.send(f"<@&{OWNER_ROLE}> Error creating event:\n```{result[1]}```")
        await interaction.response.send_message(f"Error creating event. See full response: {message.jump_url}")
    rnl.close()

def get_event_times() -> (datetime, datetime):

    # Get the current time in the Pacific time zone
    pacific_timezone = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific_timezone)

    # Calculate days until the next Friday
    days_until_friday = (4 - current_time.weekday()) % 7
    if current_time.hour > 22:
        days_until_friday += 7

    # Calculate the next Friday at 10:00 PM
    start_time = current_time.replace(hour=22, minute=0, second=0, microsecond=0) + timedelta(days=days_until_friday)

    # Calculate the end time (2 hours later)
    end_time = start_time + timedelta(hours=2)

    return (start_time, end_time)

client.run(BOT_TOKEN)