import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from vrchatapi.api import users_api

from server_constants import *
from utility import *
from utility import _authenticated_client, _vrchat_call

VRC_ID = 'vrc_id'


class RegisterCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot=bot
        self.user_data=bot.user_data



    # Register VRChat account verification command
    @app_commands.command(
        name=("debug-" if DEBUG else "") + "register",
        description="Register your VRChat account to earn exclusive rewards!"
    )
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    @app_commands.describe(
        display_name="Your VRChat display name."
    )
    async def register(self, interaction: discord.Interaction, display_name: str = None) -> None:
        # Check if the user already registered their VRChat account
        discord_id=str(interaction.user.id)
        user_record = await self.user_data.get(discord_id)
        if user_record and VRC_ID in user_record:

            vrc_id=user_record[VRC_ID]

            await interaction.response.defer(ephemeral=True) # VRChat response may take more than 3 seconds
            account=await self.get_account_from_id(vrc_id)

            # Exit if the user encountered an error
            if not account[0]:
                bot_channel=self.bot.get_channel(BOT_CHANNEL)
                error_log=(
                    f"<@&{OWNER_ROLE}> "
                    f"An error was encountered while {interaction.user.mention} attempted to use the `/register` "
                    f"command with the given display name `{display_name}` and an existing VRChat id of `{vrc_id}`. "
                    "The full VRChat response is below:\n\n"
                    f"```{account[1]}```"
                )
                await bot_channel.send(error_log)
                await interaction.followup.send(f"An error occurred while running this command. Please try again later.", ephemeral=True)
                return

            display_name=account[1].display_name
            channel=self.bot.get_channel(EVENTS_CHANNEL)
            msg=(
                f"Your VRChat account is already registered as `{display_name}`. "
                f"To change it, join an upcoming event and speak to a room owner. {channel.mention}\n\n"
                f"{self.get_key_from_name(display_name)}"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        # This user has never registered a VRChat account before
        else:

            # Show the modal input if display name wasn't provided in slash command
            if not display_name:
                class DisplayNameModal(discord.ui.Modal):
                    def __init__(self, cog: RegisterCog):
                        super().__init__(title="Register your VRChat account")
                        self.text_input=discord.ui.TextInput(label="VRChat Display Name", custom_id="display_name", placeholder="Enter your VRChat display name")
                        self.add_item(self.text_input)
                        self.cog=cog

                    async def on_submit(self, interaction: discord.Interaction):
                        display_name=self.text_input.value
                        await self.cog.register_confirm(interaction, display_name)
                        return

                await interaction.response.send_modal(DisplayNameModal(self))

            # Otherwise, if a display name was provided, initiate confirmation immediately
            else:
                await self.register_confirm(interaction, display_name)


    # Initiate the flow to confirm the user's VRChat account; assumes validation was already performed
    async def register_confirm(self, interaction: discord.Interaction, display_name: str) -> None:

        await interaction.response.defer(ephemeral=True) # VRChat response may take more than 3 seconds

        response=await self.get_account_from_name(display_name)

        # Exit if the user encountered an error
        if not response[0]:
            if response[1] is None:
                await interaction.followup.send(
                    f"Couldn't find a VRChat account with the display name `{display_name}`. "
                    "Please double-check your spelling and try again.",
                    ephemeral=True
                )
            else:
                bot_channel=self.bot.get_channel(BOT_CHANNEL)
                error_log=(
                    f"<@&{OWNER_ROLE}> "
                    f"The bot failed to look up a VRChat account while {interaction.user.mention} used `/register`. "
                    "This may mean the bot's VRChat session has expired — run `/update-roles` to re-authenticate.\n\n"
                    f"```{response[1]}```"
                )
                await bot_channel.send(error_log)
                await interaction.followup.send("An error occurred while running this command. Please try again later.", ephemeral=True)
            return

        account=response[1]
        display_name=account.display_name
        date_joined_str=""
        if account.date_joined:
            ts=int(datetime(account.date_joined.year, account.date_joined.month, account.date_joined.day, tzinfo=timezone.utc).timestamp())
            date_joined_str=f"<t:{ts}:D>"
        confirmation_text=(
            "Is this your VRChat account? Once confirmed, your account cannot be changed. "
            "Note however that it will update automatically if your display name changes in the future.\n\n"
            f"https://vrchat.com/home/user/{account.id}\n"
            f"Display name: {display_name}\n"
            f"Date joined: {date_joined_str}\n"
        )

        class ConfirmButtons(discord.ui.View):
            def __init__(self, db, bot):
                super().__init__()
                self.db=db
                self.bot=bot

            @discord.ui.button(label="Yes, that's me.", style=discord.ButtonStyle.blurple)
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.disable_buttons(interaction)

                msg=RegisterCog.get_key_from_name(display_name)
                await interaction.followup.send(msg, ephemeral=True)

                discord_id=str(interaction.user.id)
                vrc_id=account.id
                user_data=await self.db.get(discord_id)
                if not user_data:
                    user_data={}
                user_data[VRC_ID]=vrc_id
                await self.db.set(discord_id, user_data)
                await self.db.save()

                registration_channel=self.bot.get_channel(REGISTRATION_CHANNEL)
                registration_msg=(
                    f"{interaction.user.mention} has registered their VRChat display name: @{display_name}.\n"
                    f"https://vrchat.com/home/user/{account.id}"
                )
                await registration_channel.send(registration_msg)

            @discord.ui.button(label="That isn't me!", style=discord.ButtonStyle.red)
            async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.disable_buttons(interaction)

                msg="Please rerun the `/register` command to finish registering your VRChat account with the correct display name."
                await interaction.followup.send(msg, ephemeral=True)

            async def disable_buttons(self, interaction: discord.Interaction):
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled=True
                await interaction.response.defer()
                await interaction.edit_original_response(view=self)


        await interaction.followup.send(content=confirmation_text, view=ConfirmButtons(self.user_data, self.bot), ephemeral=True)

    @staticmethod
    def get_key_from_name(display_name) -> str:
        salt=DOTENV["HASH_SALT"]
        code=string_hash(display_name + salt)
        return (
            "Enter the code below in ^CrescentNightclub to access the Discord Suite!\n"
            f"# **`{code}`**"
        )

    @staticmethod
    async def get_account_from_name(display_name) -> (bool, object):
        return await asyncio.to_thread(RegisterCog._fetch_account_by_name, display_name)

    @staticmethod
    def _fetch_account_by_name(display_name) -> (bool, object):
        # VRChat no longer exposes other users' real usernames, so users are
        # looked up by display name via search.
        # Returns (True, User) on success, (False, None) if not found, (False, error_str) on error.
        try:
            with _authenticated_client() as client:
                api=users_api.UsersApi(client)
                results=_vrchat_call(api.search_users, search=display_name, n=100)
                match=next((u for u in results if u.display_name == display_name), None)
                if match is None:
                    match=next((u for u in results if u.display_name.lower() == display_name.lower()), None)
                if match is None:
                    return (False, None)
                return (True, _vrchat_call(api.get_user, match.id))
        except Exception as e:
            return (False, str(e))

    @staticmethod
    async def get_account_from_id(id) -> (bool, object):
        return await asyncio.to_thread(RegisterCog._fetch_account_by_id, id)

    @staticmethod
    def _fetch_account_by_id(id) -> (bool, object):
        try:
            with _authenticated_client() as client:
                api=users_api.UsersApi(client)
                return (True, _vrchat_call(api.get_user, id))
        except Exception as e:
            return (False, str(e))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RegisterCog(bot), guilds=[discord.Object(id=CRESCENT_MEDIA)])
