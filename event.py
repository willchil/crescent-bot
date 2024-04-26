import discord
import httpx
import pytz
from discord import app_commands
from discord.ext import commands
from RecNetLogin.recnetlogin import RecNetLogin
from server_constants import *
from utility import *
from event_templates import *


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
        (default_event, err) = await process_with_defaults({})
        if err:
            await interaction.followup.send(f"Invalid event settings: {err}", ephemeral=True)
        else:
            await self.create_recnet_event(token, interaction, default_event)
        rnl.close()

    # Register RecNet event creation command
    @app_commands.command(
        name = "custom-event",
        description = "Create an event with custom settings."
    )
    @app_commands.guilds(discord.Object(id = CRESCENT_MEDIA))
    async def custom_event(self, interaction: discord.Interaction) -> None:            
        class CustomEventModal(discord.ui.Modal):
            def __init__(self, cog: EventCog):
                super().__init__(title="Create a custom RecNet event")
                self.cog = cog

                defaults = get_main_template()

                self.name=discord.ui.TextInput(
                    label="Name",
                    custom_id=KEY_NAME,
                    placeholder=defaults[KEY_NAME],
                    required=False
                )
                self.description=discord.ui.TextInput(
                    label="Description",
                    custom_id=KEY_DESCRIPTION,
                    placeholder=defaults[KEY_DESCRIPTION],
                    required=False
                )
                self.room=discord.ui.TextInput(
                    label="Room",
                    custom_id=KEY_ROOM,
                    placeholder=defaults[KEY_ROOM],
                    required=False
                )
                self.start=discord.ui.TextInput(
                    label="Start time",
                    custom_id=KEY_START,
                    placeholder=defaults[KEY_START],
                    required=False
                )
                self.duration=discord.ui.TextInput(
                    label="Duration",
                    custom_id=KEY_DURATION,
                    placeholder=str(defaults[KEY_DURATION]),
                    required=False
                )

                self.add_item(self.name)
                self.add_item(self.description)
                self.add_item(self.room)
                self.add_item(self.start)
                self.add_item(self.duration)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer() # Room id lookup may take more than 3 seconds

                (settings, err) = await self.create_event()
                if err:
                    await interaction.followup.send(f"Invalid event settings: {err}", ephemeral=True)
                else:
                    rnl = RecNetLogin()
                    token = rnl.get_token(include_bearer=True)
                    await self.cog.create_recnet_event(token, interaction, settings)
                    rnl.close()
                return
            
            async def create_event(self):
                settings = { }
                if self.name.value:
                    settings[KEY_NAME] = self.name.value
                if self.description.value:
                    settings[KEY_DESCRIPTION] = self.description.value
                if self.room.value:
                    settings[KEY_ROOM] = self.room.value
                if self.start.value:
                    settings[KEY_START] = self.start.value
                if self.duration.value:
                    try:
                        dur = float(self.duration.value)
                    except ValueError:
                        return (None, f"Invalid duration value `{self.duration.value}`. Duration must be a number in hours.")
                    settings[KEY_DURATION] = dur
                return await process_with_defaults(settings)
            
        await interaction.response.send_modal(CustomEventModal(self))

    async def create_recnet_event(self, token, interaction: discord.Interaction, settings):

        EVENT_ENDPOINT = "https://api.rec.net/api/playerevents/v2"

        room_id = settings[KEY_ROOM_ID]

        # Convert both times to the GMT time zone
        gmt_timezone = pytz.timezone('GMT')
        start_time_gmt = settings[KEY_START_DATE].astimezone(gmt_timezone)
        end_time_gmt = settings[KEY_END_DATE].astimezone(gmt_timezone)

        # Format as "EEE, DD MMM YYYY HH:MM:SS GMT"
        start_time_str = start_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = end_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")

        payload = {
            "Name": settings[KEY_NAME],
            "Description": settings[KEY_DESCRIPTION],
            "RoomId": f"{room_id}",
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
            
            channel = self.bot.get_channel(EVENTS_CHANNEL)
            formatted_time = f"<t:{int(datetime.timestamp(settings[KEY_START_DATE]))}:t>"
            message_text = (
                f"<@&{EVENT_ROLE}> "
                f"Crescent Nightclub will be hosting an event tonight at {formatted_time}! "
                "RSVP and invite your friends below!"
                f"\n\n{eventLink}"
            )
            message = await channel.send(message_text)
            await interaction.followup.send(f"Event created. {message.jump_url}", ephemeral=True)
        
        else:
            channel = self.bot.get_channel(BOT_CHANNEL)
            message = await channel.send(f"Error creating event:\n```{response.json()}```")
            await interaction.followup.send(f"Error creating event. See full response: {message.jump_url}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot), guilds=[discord.Object(id = CRESCENT_MEDIA)])