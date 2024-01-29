import discord
import httpx
import os
import psutil
import sys
import time
from discord import app_commands
from discord.ext import commands
from git import Repo
from server_constants import CRESCENT_MEDIA


class AdminCog(commands.GroupCog, name="admin", description="A set of commands for managing the bot process."):


    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.start_time = time.time()


    @app_commands.command(name="info")
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    async def admin_info(self, interaction: discord.Interaction) -> None:

        async with httpx.AsyncClient() as client:
            ip_response = await client.get('https://ipinfo.io/json')
        ip = ip_response.json()['ip']

        msg = (
            "## System info:\n"
            f"System uptime: <t:{int(psutil.boot_time())}:R>\n"
            f"Process uptime: <t:{int(self.start_time)}:R>\n"
            f"Server IP: `{ip}`\n"
            f"Process ID: `{os.getpid()}`"
        )
        await interaction.response.send_message(msg, ephemeral=True)


    @app_commands.command(name="shutdown")
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    async def admin_shutdown(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Shutting down...", ephemeral=True)
        print("Shutting down...")
        await self.bot.close()


    @app_commands.command(name="restart")
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    async def admin_restart(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self.restart_process(interaction)


    @app_commands.command(name="update")
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    async def admin_shutdown(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.followup.send("Pulling changes...", ephemeral=True)
        repo = Repo(".")
        origin = repo.remote(name="origin")
        changes = origin.pull()
        for submodule in repo.submodules:
            submodule.update(init=True)
        if len(changes) > 0:
            updates = "### Pulled changes:\n"
            for commit in changes:
                updates += f" - {commit.name}"
            await interaction.followup.send(updates, ephemeral=True)
            await self.restart_process(interaction)
        else:
            await interaction.followup.send("Repository already up to date.", ephemeral=True)


    @staticmethod
    async def restart_process(interaction: discord.Interaction) -> None:
        await interaction.followup.send("Restarting...", ephemeral=True)
        print("Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot), guilds=[discord.Object(id=CRESCENT_MEDIA)])