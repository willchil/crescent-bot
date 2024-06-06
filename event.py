import discord
import httpx
import pytz
from discord import TextStyle, app_commands
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
            event_id = await self.create_recnet_event(token, default_event, interaction)
            await self.post_announcement(event_id, default_event[KEY_START_DATE], default_event[KEY_ANNOUNCEMENT], interaction)
        rnl.close()

    # Register RecNet event creation command
    @app_commands.command(
        name = "custom-event",
        description = "Create an event with custom settings."
    )
    @app_commands.guilds(discord.Object(id = CRESCENT_MEDIA))
    @app_commands.describe(room="Room name.")
    async def custom_event(self, interaction: discord.Interaction, room: str = None) -> None:            
        class CustomEventModal(discord.ui.Modal):
            def __init__(self, cog: EventCog, room: str):
                defaults = get_main_template()
                if not room:
                    room = defaults[KEY_ROOM]
                self.room_name = room.replace("^", "")
                super().__init__(title=f"Create an event in ^{self.room_name}")
                self.cog = cog

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
                    style=TextStyle.paragraph,
                    required=False
                )
                self.start=discord.ui.TextInput(
                    label="Start time",
                    custom_id=KEY_START,
                    placeholder=defaults[KEY_START],
                    required=False
                )
                self.duration=discord.ui.TextInput(
                    label="Duration (hours)",
                    custom_id=KEY_DURATION,
                    placeholder=str(defaults[KEY_DURATION]),
                    required=False
                )
                self.announcement=discord.ui.TextInput(
                    label="Announcement",
                    custom_id=KEY_ANNOUNCEMENT,
                    placeholder=defaults[KEY_ANNOUNCEMENT],
                    style=TextStyle.paragraph,
                    required=False
                )

                self.add_item(self.name)
                self.add_item(self.description)
                self.add_item(self.start)
                self.add_item(self.duration)
                self.add_item(self.announcement)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer() # Room id lookup may take more than 3 seconds

                (settings, err) = await self.get_settings()
                if err:
                    await interaction.followup.send(f"Invalid event settings: {err}", ephemeral=True)
                else:
                    rnl = RecNetLogin()
                    token = rnl.get_token(include_bearer=True)
                    event_id = await self.cog.create_recnet_event(token, settings, interaction)
                    await self.cog.post_announcement(event_id, settings[KEY_START_DATE], settings[KEY_ANNOUNCEMENT], interaction)
                    rnl.close()
                return
            
            async def get_settings(self):
                settings = { }
                settings[KEY_ROOM] = self.room_name
                if self.name.value:
                    settings[KEY_NAME] = self.name.value
                if self.description.value:
                    settings[KEY_DESCRIPTION] = self.description.value
                if self.start.value:
                    settings[KEY_START] = self.start.value
                if self.duration.value:
                    try:
                        dur = float(self.duration.value)
                    except ValueError:
                        return (None, f"Invalid duration value `{self.duration.value}`. Duration must be a number in hours.")
                    settings[KEY_DURATION] = dur
                if self.announcement.value:
                    settings[KEY_ANNOUNCEMENT] = self.announcement.value
                return await process_with_defaults(settings)
            
        await interaction.response.send_modal(CustomEventModal(self, room))

    async def create_recnet_event(self, token, settings, interaction: discord.Interaction) -> int:

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

        async with httpx.AsyncClient() as client:
            response = await client.post(EVENT_ENDPOINT, data=payload, headers=get_headers(token))

        # Check if the request was successful (status code 2xx)
        if response.status_code // 100 == 2:
            return response.json()["PlayerEvent"]["PlayerEventId"]
        
        else:
            channel = self.bot.get_channel(BOT_CHANNEL)
            message = await channel.send(f"Error creating event:\n```{response.json()}```")
            await interaction.followup.send(f"Error creating event. See full response: {message.jump_url}", ephemeral=True)
            return -1

    async def post_announcement(self, event_id, start_date, announcement, interaction: discord.Interaction):
        eventLink = f"https://rec.net/event/{event_id}"
        channel = self.bot.get_channel(EVENTS_CHANNEL)
        formatted_time = f"<t:{int(datetime.timestamp(start_date))}:t>"
        custom_message = announcement.replace("[TIME]", formatted_time)
        message_text = (
            f"<@&{EVENT_ROLE}> "
            f"{custom_message}"
            f"\n\n{eventLink}"
        )
        message = await channel.send(message_text)
        await message.add_reaction('<:crescent_1:1192293419557597316>')
        await interaction.followup.send(f"Event created. {message.jump_url}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot), guilds=[discord.Object(id = CRESCENT_MEDIA)])