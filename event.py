import discord
import httpx
import pytz
from discord import app_commands
from discord.ext import commands
from RecNetLogin.recnetlogin import RecNetLogin
from server_constants import *
from utility import *


class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    # Register RecNet event creation command
    @app_commands.command(
        name = "event",
        description = "Create a ^CrescentNightclub event at 10:00PM PT."
    )
    @app_commands.guilds(discord.Object(id = CRESCENT_MEDIA))
    async def event(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer() # Event creation may take more than 3 seconds
        rnl = RecNetLogin()
        token = rnl.get_token(include_bearer=True)
        (start_time, end_time) = get_event_times(22, 2) # 2 hour event, starting at 10PM
        result = await self.create_recnet_event(token, start_time, end_time)
        rnl.close()
        if result[0]:
            channel = self.bot.get_channel(EVENTS_CHANNEL)
            formatted_time = f"<t:{int(datetime.timestamp(start_time))}:t>"
            message_text = (
                f"<@&{EVENT_ROLE}> "
                f"Crescent Nightclub will be hosting an event tonight at {formatted_time}! "
                "RSVP and invite your friends below!"
                f"\n\n{result[1]}"
            )
            message = await channel.send(message_text)
            await interaction.followup.send(f"Event created. {message.jump_url}")
        else:
            channel = self.bot.get_channel(BOT_CHANNEL)
            message = await channel.send(f"Error creating event:\n```{result[1]}```")
            await interaction.followup.send(f"Error creating event. See full response: {message.jump_url}")

    @staticmethod
    async def create_recnet_event(token, start_time, end_time) -> (bool, str):

        EVENT_ENDPOINT = "https://api.rec.net/api/playerevents/v2"
        CRESCENT_NIGHTCLUB = 25357294

        # Convert both times to the GMT time zone
        gmt_timezone = pytz.timezone('GMT')
        start_time_gmt = start_time.astimezone(gmt_timezone)
        end_time_gmt = end_time.astimezone(gmt_timezone)

        # Format as "EEE, DD MMM YYYY HH:MM:SS GMT"
        start_time_str = start_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = end_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")

        payload = {
            "Name": "Party @ Crescent Nightclub",
            "Description": "Come party with us at Crescent Nightclub, one of Rec Room's most prestigious party destinations.",
            "RoomId": f"{CRESCENT_NIGHTCLUB}",
            "StartTime": start_time_str,
            "EndTime": end_time_str,
            "Accessibility": "1" # 1 for public events, 0 for private
        }

        # Uncomment for testing:
        #return (True, "https://rec.net/event/8410541010311578971")

        async with httpx.AsyncClient() as client:
            response = await client.post(EVENT_ENDPOINT, data=payload, headers=get_headers(token))

        # Check if the request was successful (status code 2xx)
        if response.status_code // 100 == 2:
            eventLink = "https://rec.net/event/" + str(response.json()["PlayerEvent"]["PlayerEventId"])
            return (True, eventLink)
        else:
            return (False, f"{response.json()}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot), guilds=[discord.Object(id = CRESCENT_MEDIA)])