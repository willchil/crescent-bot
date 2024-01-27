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
EVENTS_CHANNEL = 1188119118747013210

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
    name="event",
    description="Create a ^CrescentNightclub event at 10:00PM PT.",
    guild=discord.Object(id=CRESCENT_MEDIA)
)
async def create_event_command(interaction):
    rnl = RecNetLogin()
    token = rnl.get_token(include_bearer=True)
    (start_time, end_time) = get_event_times(22, 2) # 2 hour event, starting at 10PM
    result = await create_event(token, start_time, end_time)
    rnl.close()
    if result[0]:
        channel = client.get_channel(EVENTS_CHANNEL)
        formatted_time = f"<t:{int(datetime.timestamp(start_time))}:t>"
        message = await channel.send(f"<@&{EVENT_ROLE}> Crescent Nightclub will be hosting an event tonight at {formatted_time}! RSVP and invite your friends below!\n\n{result[1]}")
        await interaction.response.send_message(f"Event created. {message.jump_url}")
    else:
        channel = client.get_channel(BOT_CHANNEL)
        message = await channel.send(f"<@&{OWNER_ROLE}> Error creating event:\n```{result[1]}```")
        await interaction.response.send_message(f"Error creating event. See full response: {message.jump_url}")

def get_event_times(start_hour, duration) -> (datetime, datetime):

    # Get the current time in the Pacific time zone
    pacific_timezone = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific_timezone)

    # Set a date offset if next time is not until tomorrow
    day_offset = 1 if current_time.hour >= start_hour else 0

    # Calculate the next time it's the start hour
    start_time = current_time.replace(hour=start_hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)

    # Calculate the end time
    end_time = start_time + timedelta(hours=duration)

    return (start_time, end_time)

client.run(BOT_TOKEN)