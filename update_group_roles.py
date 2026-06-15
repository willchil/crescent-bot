"""
Fetches VRChat group members with 'Group Owner', 'Admin', or 'Moderator' roles
and pushes a JSON object of display names per role to a GitHub Gist.

Requires VRCHAT_USERNAME and VRCHAT_PASSWORD in .env.secret.
These are credentials for the bot's own VRChat account — never collect credentials
from other users, per VRChat API guidelines.

After the first login (which may require an email OTP), the auth cookie is saved
to .env.secret as VRCHAT_AUTH_COOKIE and reused on subsequent runs.
Requires GITHUB_TOKEN in .env.secret with the 'gist' scope.
"""

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from datetime import time as dt_time
from zoneinfo import ZoneInfo

import discord
import vrchatapi
from discord import app_commands
from discord.ext import commands, tasks
from server_constants import BOT_CHANNEL, BOT_OWNER, CRESCENT_MEDIA
from vrchatapi.api import authentication_api, groups_api
from vrchatapi.exceptions import ApiException, UnauthorizedException
from vrchatapi.models import TwoFactorAuthCode, TwoFactorEmailCode
from dotenv import dotenv_values

GROUP_ID = "grp_d57a5835-6e73-4a99-a63b-084c0178b18c"
BOT_USER = "usr_cb51592e-7915-4c35-bedb-8d62ef6288ce"
TARGET_ROLES = {"Group Owner", "Admin", "Moderator"}  # Group Owner is merged into next role
ENV_FILE = ".env.secret"
GIST_ID = "68b90018fc4554a18a56026776510336"
GIST_API = f"https://api.github.com/gists/{GIST_ID}"


# --- Rate limiting ---

def _vrchat_call(fn, *args, **kwargs):
    """Call a VRChat SDK method with exponential back-off on 429."""
    for attempt in range(8):
        try:
            return fn(*args, **kwargs)
        except ApiException as e:
            if e.status == 429 and attempt < 3:
                wait = 2 ** attempt
                print(f"Rate limited (429), retrying in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise


# --- Auth cookie helpers ---

def _save_auth_cookie(cookie_value: str) -> None:
    with open(ENV_FILE, "r") as f:
        contents = f.read()
    if re.search(r"^VRCHAT_AUTH_COOKIE=", contents, re.MULTILINE):
        contents = re.sub(r"^VRCHAT_AUTH_COOKIE=.*$", f"VRCHAT_AUTH_COOKIE={cookie_value}", contents, flags=re.MULTILINE)
    else:
        contents = contents.rstrip("\n") + f"\nVRCHAT_AUTH_COOKIE={cookie_value}\n"
    with open(ENV_FILE, "w") as f:
        f.write(contents)


def _extract_auth_cookie(client: vrchatapi.ApiClient) -> str | None:
    for cookie in client.rest_client.cookie_jar:
        if cookie.name == "auth":
            return cookie.value
    return None


def _try_cookie_auth(client: vrchatapi.ApiClient, auth_cookie: str) -> str | None:
    """Attempt auth with a saved cookie. Returns display name on success, None on failure."""
    import http.cookiejar
    client.rest_client.cookie_jar.clear()
    client.rest_client.cookie_jar.set_cookie(http.cookiejar.Cookie(
        version=0, name="auth", value=auth_cookie, port=None, port_specified=False,
        domain="api.vrchat.cloud", domain_specified=True, domain_initial_dot=False,
        path="/", path_specified=True, secure=True, expires=None, discard=False,
        comment=None, comment_url=None, rest={},
    ))
    try:
        return _vrchat_call(authentication_api.AuthenticationApi(client).get_current_user).display_name
    except Exception:
        return None


# --- VRChat auth ---

def login(client: vrchatapi.ApiClient, code_provider=None) -> str:
    """Login with username/password, handling email OTP if required. Saves the auth cookie.

    code_provider: callable(prompt) -> str that supplies a 2FA code when needed.
    Defaults to input() for standalone use. Pass a custom callable for headless or
    Discord-interactive contexts.
    """
    if code_provider is None:
        code_provider = input
    auth_api = authentication_api.AuthenticationApi(client)
    try:
        current_user = _vrchat_call(auth_api.get_current_user)
    except UnauthorizedException as e:
        if e.status == 200:
            if "Email 2 Factor Authentication" in e.reason:
                _vrchat_call(auth_api.verify2_fa_email_code,
                    two_factor_email_code=TwoFactorEmailCode(code_provider("Email 2FA code: ")))
            elif "2 Factor Authentication" in e.reason:
                _vrchat_call(auth_api.verify2_fa,
                    two_factor_auth_code=TwoFactorAuthCode(code_provider("TOTP 2FA code: ")))
            current_user = _vrchat_call(auth_api.get_current_user)
        else:
            raise RuntimeError(
                "VRChat login failed (401) — check VRCHAT_USERNAME and VRCHAT_PASSWORD in .env.secret."
            ) from e

    cookie = _extract_auth_cookie(client)
    if cookie:
        _save_auth_cookie(cookie)

    return current_user.display_name


# --- VRChat group queries ---

def get_roles(client: vrchatapi.ApiClient) -> dict[str, str]:
    api = groups_api.GroupsApi(client)
    all_roles = _vrchat_call(api.get_group_roles, GROUP_ID)
    return {r.id: r.name for r in all_roles if r.name in TARGET_ROLES}


def get_members_by_role(client: vrchatapi.ApiClient, role_id: str) -> list[tuple[str, str]]:
    api = groups_api.GroupsApi(client)
    results, offset, limit = [], 0, 100
    while True:
        page = _vrchat_call(api.get_group_members, GROUP_ID, n=limit, offset=offset, role_id=role_id)
        for m in page:
            display_name = (m.user.display_name if m.user else None) or m.user_id
            results.append((m.user_id, display_name))
        if len(page) < limit:
            break
        offset += limit
        time.sleep(0.5)  # be respectful between paginated requests
    return results


# --- Gist update ---

def _gist_headers(github_token: str) -> dict:
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def push_to_gist(data: dict, github_token: str | None = None) -> None:
    if not github_token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set in .env.secret.\n"
            "Create one at github.com → Settings → Developer settings → Personal access tokens\n"
            "with the 'gist' scope, then add GITHUB_TOKEN=ghp_... to .env.secret."
        )

    content = json.dumps(data, indent=2) + "\n"
    headers = _gist_headers(github_token)

    # Fetch current content to skip the update if nothing changed
    try:
        with urllib.request.urlopen(urllib.request.Request(GIST_API, headers=headers)) as resp:
            gist = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error fetching gist ({e.code}): {e.read().decode()}") from e

    current = gist.get("files", {}).get("roles.json", {}).get("content", "")
    if content == current:
        print("roles.json is already up to date.")
        return

    payload = json.dumps({"files": {"roles.json": {"content": content}}}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(GIST_API, data=payload, method="PATCH", headers=headers)) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error updating gist ({e.code}): {e.read().decode()}") from e

    print("Updated roles.json on gist.")


# --- Main ---

def main(code_provider=None):
    env = dotenv_values(ENV_FILE)
    username = env.get("VRCHAT_USERNAME")
    password = env.get("VRCHAT_PASSWORD")
    if not username or not password:
        raise RuntimeError("VRCHAT_USERNAME and VRCHAT_PASSWORD must be set in .env.secret.")

    configuration = vrchatapi.Configuration(username=username, password=password)

    with vrchatapi.ApiClient(configuration) as client:
        client.user_agent = "CrescentBot/1.0 willchil@icloud.com"

        saved_cookie = env.get("VRCHAT_AUTH_COOKIE")
        display_name = _try_cookie_auth(client, saved_cookie) if saved_cookie else None
        if display_name is None:
            display_name = login(client, code_provider=code_provider)

        print(f"Authenticated as: {display_name}\n", flush=True)
        print(f"Fetching roles for group {GROUP_ID}...", flush=True)

        role_map = get_roles(client)
        if not role_map:
            print("No matching roles found. Check that the role names match exactly.")
            return

        by_role: dict[str, list[tuple[str, str]]] = {}
        for role_id, role_name in role_map.items():
            members = get_members_by_role(client, role_id)
            by_role.setdefault(role_name, [])
            seen = {uid for uid, _ in by_role[role_name]}
            for user_id, name in members:
                if user_id not in seen and user_id != BOT_USER:
                    by_role[role_name].append((user_id, name))
                    seen.add(user_id)
            time.sleep(0.5)  # brief pause between role queries

        if "Group Owner" in by_role:
            target = "Admin" if "Admin" in by_role else next(iter(by_role), None)
            if target:
                seen_in_target = {uid for uid, _ in by_role[target]}
                for user_id, name in by_role.pop("Group Owner"):
                    if user_id not in seen_in_target:
                        by_role[target].append((user_id, name))
                        seen_in_target.add(user_id)

        result = {role_name: sorted(name for _, name in members) for role_name, members in by_role.items()}
        print(json.dumps(result, indent=2))

        push_to_gist(result, env.get("GITHUB_TOKEN"))


if __name__ == "__main__":
    main()


# --- Discord cog ---

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
                await channel.send(f"<@{BOT_OWNER}> Group roles update failed:\n\n```\n{e}\n```")

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
