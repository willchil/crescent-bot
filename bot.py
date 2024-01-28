import discord
from utility import get_event_times
from utility import string_hash
from event_creator import create_event
from RecNetLogin.recnetlogin import RecNetLogin
from register import get_account
from discord import app_commands
from datetime import datetime
from dotenv import dotenv_values


CRESCENT_MEDIA = 1188116803814162522
EVENT_ROLE = 1188332286500933713
OWNER_ROLE = 1188119778611712040
BOT_CHANNEL = 1194502014244225164
EVENTS_CHANNEL = 1188119118747013210

DOTENV = dotenv_values(".env.secret")
BOT_TOKEN = DOTENV["BOT_TOKEN"]
HASH_SALT = DOTENV["HASH_SALT"]


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
    await interaction.response.defer() # Event creation may take more than 3 seconds
    rnl = RecNetLogin()
    token = rnl.get_token(include_bearer=True)
    (start_time, end_time) = get_event_times(22, 2) # 2 hour event, starting at 10PM
    result = await create_event(token, start_time, end_time)
    rnl.close()
    if result[0]:
        channel = client.get_channel(EVENTS_CHANNEL)
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
        channel = client.get_channel(BOT_CHANNEL)
        message = await channel.send(f"Error creating event:\n```{result[1]}```")
        await interaction.followup.send(f"Error creating event. See full response: {message.jump_url}")


# Register RecNet event creation command
@tree.command(
    name="register",
    description="Register your Rec Room account to earn exclusive rewards!",
    guild=discord.Object(id=CRESCENT_MEDIA)
)
@app_commands.describe(
    username="Your Rec Room username."
)
async def register_command(interaction, username: str):
    await interaction.response.defer() # RecNet response may take more than 3 seconds
    rnl = RecNetLogin()
    token = rnl.get_token(include_bearer=True)
    response = await get_account(username, token)
    rnl.close()

    # Exit if the user encountered an error
    if not response[0]:
        bot_channel = client.get_channel(BOT_CHANNEL)
        error_log = (
            f"<@&{OWNER_ROLE}> "
            f"An error was encountered while {interaction.account} attempted to use the `/register` command with the username `{username}`. "
            "The full RecNet response is below:\n\n"
            f"```{response[1]}```"
        )
        await bot_channel.send(error_log)
        await interaction.followup.send(f"An error occurred while running this command. Please try again later.")
        return
    
    account = response[1]
    date_created = datetime.strptime(account['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%B %d, %Y")
    confirmation_text = (
        "Is this your Rec Room account? Once confirmed, your account cannot be changed. "
        "Note however that it will update automatically if your username changes in the future.\n\n"
        f"https://rec.net/user/{username}\n"
        f"Username: {account['username']}\n"
        f"Display name: {account['displayName']}\n"
        f"Date created: {date_created}\n"
    )

    class confirm_buttons(discord.ui.View):
        def __init__(self):
            super().__init__()

        @discord.ui.button(label="Yes, that's me.", style=discord.ButtonStyle.blurple)
        async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            code = string_hash(username + HASH_SALT)
            msg = (
                "Enter the code below in ^CrescentNightclub to earn exclusive rewards!\n"
                f"# **`{code}`**"
            )
            await interaction.response.send_message(msg, ephemeral=True)

            # TODO: Save the account id to the database
            id = int(account['accountId'])

        @discord.ui.button(label="That isn't me!", style=discord.ButtonStyle.red)
        async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            msg = "Please rerun the `/register` command to finish registering your Rec Room account with the correct username."
            await interaction.response.send_message(msg, ephemeral=True)

    await interaction.followup.send(content=confirmation_text, view=confirm_buttons(), ephemeral=True)


client.run(BOT_TOKEN)