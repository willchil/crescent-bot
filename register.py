import discord
import httpx
import pickledb
from discord import app_commands
from discord.ext import commands
from RecNetLogin.src.recnetlogin import RecNetLogin
from server_constants import *
from utility import *


class RegisterCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot=bot
        self.db=pickledb.load('user_data.db', True)

    REC_ID='rec_id'


    # Register RecNet event creation command
    @app_commands.command(
        name=("debug-" if DEBUG else "") + "register",
        description="Register your Rec Room account to earn exclusive rewards!"
    )
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    @app_commands.describe(
        username="Your Rec Room username."
    )
    async def register(self, interaction: discord.Interaction, username: str = None) -> None:
        # Check if the user already registered their Rec Room account
        discord_id=str(interaction.user.id)
        if self.db.exists(discord_id) and self.db.dexists(discord_id, self.REC_ID):

            await interaction.response.defer(ephemeral=True) # RecNet response may take more than 3 seconds

            rec_id=self.db.dget(discord_id, self.REC_ID)

            account=await self.get_account_from_id(rec_id)

            # Exit if the user encountered an error
            if not account[0]:
                bot_channel=self.bot.get_channel(BOT_CHANNEL)
                error_log=(
                    f"<@&{OWNER_ROLE}> "
                    f"An error was encountered while {interaction.user.mention} attempted to use the `/register` "
                    f"command with the given username `{username}` and an existing RecNet id of `{rec_id}`. "
                    "The full RecNet response is below:\n\n"
                    f"```{account[1]}```"
                )
                await bot_channel.send(error_log)
                await interaction.followup.send(f"An error occurred while running this command. Please try again later.", ephermal=True)
                return
            
            username=account[1]['username']
            channel=self.bot.get_channel(EVENTS_CHANNEL)
            msg=(
                f"Your Rec Room account is already registered as `{username}`. "
                f"To change it, join an upcoming event and speak to a room owner. {channel.mention}\n\n"
                f"{self.get_key_from_name(username)}"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return
        
        # This user has never registered a RecNet account before
        else:

            # Show the modal input if using the context menu, or username wasn't provided in slash command
            if not username:
                class UsernameModal(discord.ui.Modal):
                    def __init__(self, cog: RegisterCog):
                        super().__init__(title="Register your Rec Room account")
                        self.text_input=discord.ui.TextInput(label="Rec Room Username", custom_id="username", placeholder="Enter your Rec Room username")
                        self.add_item(self.text_input)
                        self.cog=cog

                    async def on_submit(self, interaction: discord.Interaction):
                        username=self.text_input.value
                        await self.cog.register_confirm(interaction, username)
                        return
                    
                await interaction.response.send_modal(UsernameModal(self))

            # Otherwise, if a username was provided, initiate confirmation immediately
            else:
                await self.register_confirm(interaction, username)


    # Initiate the flow to confirm the user's RecNet account; assumes validation was already performed
    async def register_confirm(self, interaction: discord.Interaction, username: str) -> None:

        await interaction.response.defer(ephemeral=True) # RecNet response may take more than 3 seconds

        response=await self.get_account_from_name(username)

        # Exit if the user encountered an error
        if not response[0]:
            bot_channel=self.bot.get_channel(BOT_CHANNEL)
            error_log=(
                f"<@&{OWNER_ROLE}> "
                f"An error was encountered while {interaction.user.mention} attempted to use the `/register` command with the username `{username}`. "
                "The full RecNet response is below:\n\n"
                f"```{response[1]}```"
            )
            await bot_channel.send(error_log)
            await interaction.followup.send(f"An error occurred while running this command. Please try again later.", ephemeral=True)
            return
        
        account=response[1]
        username=account['username']
        timestamp = account['createdAt'][:-1][:24] + 'Z' # Old accounts only have two decimals of second precision
        date_created=datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%B %d, %Y")
        confirmation_text=(
            "Is this your Rec Room account? Once confirmed, your account cannot be changed. "
            "Note however that it will update automatically if your username changes in the future.\n\n"
            f"https://rec.net/user/{username}\n"
            f"Username: {username}\n"
            f"Display name: {account['displayName']}\n"
            f"Date created: {date_created}\n"
        )

        class ConfirmButtons(discord.ui.View):
            def __init__(self, db, bot):
                super().__init__()
                self.db=db
                self.bot=bot

            @discord.ui.button(label="Yes, that's me.", style=discord.ButtonStyle.blurple)
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.disable_buttons(interaction)
                
                msg=RegisterCog.get_key_from_name(username)
                await interaction.followup.send(msg, ephemeral=True)

                discord_id=str(interaction.user.id)
                rec_id=int(account['accountId'])
                user_data=self.db.get(discord_id)
                if not user_data:
                    user_data={}
                user_data[RegisterCog.REC_ID]=rec_id
                self.db.set(discord_id, user_data)

                registration_channel=self.bot.get_channel(REGISTRATION_CHANNEL)
                registration_msg=(
                    f"{interaction.user.mention} has registered their Rec Room username: @{username}.\n"
                    f"https://rec.net/user/{username}"
                )
                await registration_channel.send(registration_msg)

            @discord.ui.button(label="That isn't me!", style=discord.ButtonStyle.red)
            async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.disable_buttons(interaction)

                msg="Please rerun the `/register` command to finish registering your Rec Room account with the correct username."
                await interaction.followup.send(msg, ephemeral=True)

            async def disable_buttons(self, interaction: discord.Interaction):
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled=True                
                await interaction.response.defer()
                await interaction.edit_original_response(view=self)

        
        await interaction.followup.send(content=confirmation_text, view=ConfirmButtons(self.db, self.bot), ephemeral=True)

    @staticmethod
    def get_key_from_name(username) -> str:
        salt=DOTENV["HASH_SALT"]
        code=string_hash(username + salt)
        return (
            "Enter the code below in ^CrescentNightclub to access the Discord Suite!\n"
            f"# **`{code}`**"
        )

    @staticmethod
    async def get_account_from_name(username) -> (bool, str):

        token=DOTENV["RN_SUBSCRIPTION_KEY"]
        if token:
            account_endpoint=f"https://apim.rec.net/public/accounts/?username={username}"
            async with httpx.AsyncClient() as client:
                response=await client.get(account_endpoint, headers=get_headers_official(token))
        else:
            rnl=RecNetLogin()
            token=rnl.get_token(include_bearer=True)
            account_endpoint=f"https://accounts.rec.net/account?username={username}"
            async with httpx.AsyncClient() as client:
                response=await client.get(account_endpoint, headers=get_headers_rnl(token))
            rnl.close()

        # Check if the request was successful (status code 2xx)
        success=response.status_code // 100 == 2
        return (success, response.json())
    
    @staticmethod
    async def get_account_from_id(id) -> (bool, str):

        token=DOTENV["RN_SUBSCRIPTION_KEY"]
        if token:
            account_endpoint=f"https://apim.rec.net/public/accounts/{id}"
            async with httpx.AsyncClient() as client:
                response=await client.get(account_endpoint, headers=get_headers_official(token))
        else:
            rnl=RecNetLogin()
            token=rnl.get_token(include_bearer=True)
            account_endpoint=f"https://accounts.rec.net/account/{id}"
            async with httpx.AsyncClient() as client:
                response=await client.get(account_endpoint, headers=get_headers_rnl(token))
            rnl.close()

        # Check if the request was successful (status code 2xx)
        success=response.status_code // 100 == 2
        return (success, response.json())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RegisterCog(bot), guilds=[discord.Object(id=CRESCENT_MEDIA)])