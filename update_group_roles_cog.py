import asyncio
from datetime import time as dt_time
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from server_constants import BOT_CHANNEL, BOT_OWNER, CRESCENT_MEDIA
from update_group_roles import main

PACIFIC = ZoneInfo("America/Los_Angeles")


def _headless_code_provider(_prompt: str) -> str:
    raise RuntimeError(
        "VRChat login requires a 2FA code but the bot is running headless. "
        "Re-run the script manually to cache a fresh VRCHAT_AUTH_COOKIE in .env.secret."
    )


class UpdateGroupRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.update_task.start()

    def cog_unload(self) -> None:
        self.update_task.cancel()

    async def _run_update(self, interaction: discord.Interaction | None = None) -> None:
        """Run main() in a thread with the appropriate 2FA code_provider.

        interaction=None → headless (raise on 2FA).
        interaction provided → collect the code via a Discord modal dialog.
        """
        if interaction is not None:
            loop = asyncio.get_running_loop()

            def discord_code_provider(prompt: str) -> str:
                async def ask_via_modal() -> str:
                    code_future: asyncio.Future[str] = loop.create_future()

                    class TwoFAModal(discord.ui.Modal, title="VRChat 2FA Code"):
                        code_input = discord.ui.TextInput(
                            label=prompt.rstrip(": "),
                            placeholder="6-digit code",
                            min_length=1,
                            max_length=20,
                        )

                        async def on_submit(self, modal_interaction: discord.Interaction) -> None:
                            await modal_interaction.response.defer()
                            if not code_future.done():
                                code_future.set_result(self.code_input.value.strip())

                    class ModalView(discord.ui.View):
                        def __init__(self) -> None:
                            super().__init__(timeout=120.0)

                        @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.primary)
                        async def open_modal(self, btn_interaction: discord.Interaction, _button: discord.ui.Button) -> None:
                            await btn_interaction.response.send_modal(TwoFAModal())

                    await interaction.followup.send(
                        f"<@{interaction.user.id}> VRChat login requires a 2FA code.",
                        view=ModalView(),
                        ephemeral=True,
                    )
                    return await asyncio.wait_for(code_future, timeout=120.0)

                return asyncio.run_coroutine_threadsafe(ask_via_modal(), loop).result(timeout=130.0)

            code_provider = discord_code_provider
        else:
            code_provider = _headless_code_provider

        await asyncio.to_thread(main, code_provider=code_provider)

    @tasks.loop(time=[
        dt_time(hour=9, minute=47, tzinfo=PACIFIC),
        dt_time(hour=21, minute=47, tzinfo=PACIFIC),
    ])
    async def update_task(self) -> None:
        print("Running scheduled group roles update...", flush=True)
        try:
            await self._run_update()
        except Exception as e:
            print(f"Group roles update failed: {e}", flush=True)
            channel = self.bot.get_channel(BOT_CHANNEL)
            if channel:
                msg = f"<@{BOT_OWNER}> Group roles update failed:\n\n```\n{e}\n```"
                if "2FA" in str(e):
                    msg += "\n\nRun `/update-roles` to enter the 2FA code interactively."
                await channel.send(msg)

    @update_task.before_loop
    async def before_update_task(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="update-roles", description="Manually trigger a VRChat group roles update.")
    @app_commands.guilds(discord.Object(id=CRESCENT_MEDIA))
    async def update_roles_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self._run_update(interaction=interaction)
            await interaction.followup.send("Group roles updated successfully.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Update failed: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UpdateGroupRolesCog(bot))
