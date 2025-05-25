import discord
import httpx
import pytz
import re
from discord import TextStyle, app_commands, Message
from discord.ext import commands
from RecNetLogin.src.recnetlogin import RecNetLogin
from server_constants import *
from utility import *
from event_templates import *
from register import REC_ID


class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    # Register RecNet event creation command
    @app_commands.command(
        name = ("debug-" if DEBUG else "") + "event",
        description = "Create a ^CrescentNightclub event at 10:00PM PT and post an announcement."
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
            (event_id, created) = await self.create_recnet_event(token, default_event, interaction)
            if created:
                announcement = await self.post_announcement(event_id, default_event[KEY_START_DATE], default_event[KEY_ANNOUNCEMENT])
                response = (
                    f"Event created: {created.jump_url}\n"
                    f"Announcement posted: {announcement.jump_url}"
                )
                await interaction.followup.send(response, ephemeral=True)
        rnl.close()

    # Register RecNet event creation command
    @app_commands.command(
        name = ("debug-" if DEBUG else "") + "custom-event",
        description = "Create an event with custom settings."
    )
    @app_commands.guilds(discord.Object(id = CRESCENT_MEDIA))
    @app_commands.describe(room="Room name.")
    async def custom_event(self, interaction: discord.Interaction, room: str = None) -> None:            
        class CustomEventModal(discord.ui.Modal):
            def __init__(self, cog: EventCog, room: str):
                defaults = get_main_template()
                self.room_name = room.replace("^", "") if room else ""
                super().__init__(title="Create a custom RecNet event")
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
                self.room=discord.ui.TextInput(
                     label="Room",
                     custom_id=KEY_ROOM,
                     placeholder=defaults[KEY_ROOM],
                     default=self.room_name,
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

                self.add_item(self.name)
                self.add_item(self.description)
                self.add_item(self.room)
                self.add_item(self.start)
                self.add_item(self.duration)


            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer() # Room id lookup may take more than 3 seconds

                (settings, err) = await self.get_settings()
                if err:
                    await interaction.followup.send(f"Invalid event settings: {err}", ephemeral=True)
                else:
                    rnl = RecNetLogin()
                    token = rnl.get_token(include_bearer=True)
                    (_, event_message) = await self.cog.create_recnet_event(token, settings, interaction)
                    rnl.close()
                    await interaction.followup.send(content=f"Event created: {event_message.jump_url}", ephemeral=True)
            
            async def get_settings(self):
                settings = { }
                if self.name.value:
                    settings[KEY_NAME] = self.name.value
                if self.description.value:
                    settings[KEY_DESCRIPTION] = self.description.value
                if self.name.value:
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

        await interaction.response.send_modal(CustomEventModal(self, room))

    # Post an announcement for the event linked in the replied post
    @app_commands.command(
        name = ("debug-" if DEBUG else "") + "announce-event",
        description = "Announce a specified or upcoming event."
    )
    @app_commands.guilds(discord.Object(id = CRESCENT_MEDIA))
    @app_commands.describe(event_link="RecNet link or event id.")
    async def announce_event(self, interaction: discord.Interaction, event_link: str = None) -> None:

        class EventAnnouncementModal(discord.ui.Modal):
            def __init__(self, cog: EventCog, event_id: int):
                self.defaults = get_main_template()
                self.event_id = event_id
                super().__init__(title=f"Create an event announcement")
                self.cog = cog

                self.announcement=discord.ui.TextInput(
                    label="Announcement",
                    custom_id=KEY_ANNOUNCEMENT,
                    placeholder=self.defaults[KEY_ANNOUNCEMENT],
                    style=TextStyle.paragraph,
                    required=False
                )
                self.add_item(self.announcement)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer() # Event lookup may take more than 3 seconds
                event_data = await get_event_data(event_id)
                start_date = get_event_start(event_data)
                if not start_date:
                    await interaction.followup.send(f"Could not get start date from RecNet for event `{event_id}`.", ephemeral=True)
                    return
                announcement = await self.cog.post_announcement(event_id, start_date, self.announcement.value or self.defaults[KEY_ANNOUNCEMENT])
                await interaction.followup.send(f"Event announcement posted: {announcement.jump_url}", ephemeral=True)

        def extract_event_id(text: str) -> int:
            pattern = r"https://rec\.net/event/(\d+)"
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
            try:
                return int(text.strip())
            except ValueError:
                return None


        # If an event link was provided, try to extract the event id from it directly
        if event_link:
            event_id = extract_event_id(event_link)
        else:
            # Fallback to getting the user's upcoming event if no link is provided
            discord_id=str(interaction.user.id)
            if self.bot.user_data.exists(discord_id) and self.bot.user_data.dexists(discord_id, REC_ID):
                rec_id = self.bot.user_data.dget(discord_id, REC_ID)
                event_id = await get_next_event_by_player(rec_id)         

        # Display an error and return if the event id is invalid
        if not event_id:
            await interaction.response.send_message(
                "No RecNet event found. To announce an event:\n"
                "- Include the link in the `event_link` parameter, or\n"
                "- Register your Rec Room account with the `/register` command to automatically find your upcoming RecNet event.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_modal(EventAnnouncementModal(self, event_id))



    async def create_recnet_event(self, token, settings, interaction: discord.Interaction) -> (int, Message):

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
            "Accessibility": f"{0 if DEBUG else 1}" # 1 for public events, 0 for private
        }

        def get_created_text(id: int) -> str:
            return (
                f"**Event created:** {self.get_event_link(id)}\n\n"
                f"**Name:** {settings[KEY_NAME]}\n"
                f"**Description:**\n> {settings[KEY_DESCRIPTION]}\n"
                f"**Start:** {self.get_formatted_time(settings[KEY_START_DATE], 'f')}\n"
                f"**End:** {self.get_formatted_time(settings[KEY_START_DATE]+timedelta(hours=settings[KEY_DURATION]), 'f')}\n"
            )
        channel = self.bot.get_channel(BOT_CHANNEL)

        # Don't actually create new event while debugging
        if DEBUG:
            return (707287540578574014, await channel.send(get_created_text(707287540578574014)))

        async with httpx.AsyncClient() as client:
            response = await client.post(EVENT_ENDPOINT, data=payload, headers=get_headers_official(token))

        # Check if the request was successful (status code 2xx)
        if response.status_code // 100 == 2:
            event_id = response.json()["PlayerEvent"]["PlayerEventId"]
            created_text = get_created_text(event_id)
            return (event_id, await channel.send(created_text))
        
        else:
            message = await channel.send(f"Error creating event:\n\n```\n{response.json()}\n```")
            await interaction.followup.send(f"Error creating event. See full response: {message.jump_url}", ephemeral=True)
            return (-1, None)


    async def post_announcement(self, event_id, start_date, announcement) -> Message:
        eventLink = self.get_event_link(event_id)
        channel = self.bot.get_channel(EVENTS_CHANNEL)
        formatted_time = self.get_formatted_time(start_date)
        custom_message = announcement.replace("[TIME]", formatted_time).replace("[time]", formatted_time).replace("[Time]", formatted_time)
        message_text = (
            f"<@&{EVENT_ROLE}> "
            f"{custom_message}"
            f"\n\n{eventLink}"
        )
        message = await channel.send(message_text)
        await message.add_reaction(CRESCENT_REACTION)
        return message

    @staticmethod
    def get_event_link(event_id: int) -> str:
        return f"https://rec.net/event/{event_id}"
    
    @staticmethod
    def get_formatted_time(start_date: int, format: str = "t") -> str:
        return f"<t:{int(datetime.timestamp(start_date))}:{format}>"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot), guilds=[discord.Object(id = CRESCENT_MEDIA)])