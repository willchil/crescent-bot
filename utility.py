import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from dateutil import parser
from dotenv import dotenv_values
import httpx
import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import ApiException, UnauthorizedException
from vrchatapi.models import TwoFactorAuthCode, TwoFactorEmailCode

from server_constants import DOTENV

def parse_event_times(date_time_str, hours) -> (datetime, datetime, str):
    MAX_HOURS = 4
    if hours > MAX_HOURS:
        return (None, None, f"Event cannot be longer than {MAX_HOURS} hours.")
    elif hours <= 0:
        return (None, None, "Event duration must be positive.")

    try:
        start_time = parser.parse(date_time_str)
    except parser.ParserError:
        return (None, None, f"Could not parse start time: `{date_time_str}`")

    now = datetime.now()
    
    if (start_time.date() < now.date()):
        return (None, None, f"Start date has already passed: `{start_time}`")

    if start_time.date() == now.date() and start_time.time() < now.time():
        start_time += timedelta(days=1)

    end_time = start_time + timedelta(hours=hours)

    return start_time, end_time, None


def get_headers_official(token) -> str:
    return {
        'Cache-Control': 'no-cache',
        'Api-Version': 'v1',
        'Ocp-Apim-Subscription-Key': token
    }


def string_hash(input) -> str:

    def rotate_right(val, r_bits):
        val &= 0xFFFFFFFF
        r_bits &= 31
        return ((val >> r_bits) | (val << (32 - r_bits))) & 0xFFFFFFFF

    result = 0xFFFFFFFF  # Initialize 'result' to all positive bits
    for i, ch in enumerate(input):  # For each character in the string
        ascii_val = ord(ch)  # Convert the character to its ASCII byte
        shift_count = (12 * i + 7) % 32  # Ensure shift count is between 0 and 31
        rotated_val = rotate_right(ascii_val, shift_count)
        result ^= rotated_val  # Bit xor with 'result'

    hex_str = hex(result & 0xFFFFFFFF)[2:].zfill(8) # Convert 'result' to hexadecimal
    hex_str = hex_str[:6] # Ensure the hexadecimal string is 6 digits long
    return hex_str  # Return the hexadecimal string


async def get_room_id(room: str) -> int:
    endpoint = f"https://rooms.rec.net/rooms?name={room}"
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint)

    if response.status_code // 100 == 2:
        return response.json()["RoomId"]
    else:
        return -1


async def get_event_data(event_id: int) -> datetime:
    token=DOTENV["RN_SUBSCRIPTION_KEY"]
    headers = get_headers_official(token)
    endpoint = f"https://apim.rec.net/public/playerevents/{event_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, headers=headers)

    if response.status_code // 100 == 2:
        return response.json()
    else:
        return None


async def get_next_event_by_player(player_id: int) -> int:
    token=DOTENV["RN_SUBSCRIPTION_KEY"]
    headers = get_headers_official(token)
    endpoint = f"https://apim.rec.net/public/playerevents/creator/{player_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, headers=headers)

    if response.status_code // 100 != 2:
        return None
    
    now = datetime.now(timezone.utc)
    future_events = [
        event for event in response.json()
        if get_event_start(event) > now
    ]
    
    if not future_events:
        return None

    earliest_event = min(
        future_events,
        key=lambda event: get_event_start(event)
    )

    return int(earliest_event['PlayerEventId'])


def get_event_start(event) -> datetime:
    start_str = event["StartTime"]
    timestamp = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ")
    timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp


# --- VRChat auth ---

ENV_FILE = ".env.secret"


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


def _headless_code_provider(_prompt: str) -> str:
    raise RuntimeError(
        "VRChat login requires a 2FA code but the bot is running headless. "
        "Run update_group_roles.py manually to cache a fresh VRCHAT_AUTH_COOKIE in .env.secret."
    )


@contextmanager
def _authenticated_client():
    """Yield a VRChat ApiClient authenticated as the bot's own account.

    Reuses the saved VRCHAT_AUTH_COOKIE (kept fresh by the scheduled group roles
    update); falls back to a username/password login, raising on 2FA since this
    runs headless inside the bot.
    """
    env = dotenv_values(ENV_FILE)
    bot_username = env.get("VRCHAT_USERNAME")
    password = env.get("VRCHAT_PASSWORD")
    if not bot_username or not password:
        raise RuntimeError("VRCHAT_USERNAME and VRCHAT_PASSWORD must be set in .env.secret.")

    configuration = vrchatapi.Configuration(username=bot_username, password=password)
    with vrchatapi.ApiClient(configuration) as client:
        client.user_agent = f"CrescentBot/1.0 {env.get('CONTACT_EMAIL')}"
        saved_cookie = env.get("VRCHAT_AUTH_COOKIE")
        if not (saved_cookie and _try_cookie_auth(client, saved_cookie)):
            login(client, code_provider=_headless_code_provider)
        yield client