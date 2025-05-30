from datetime import datetime, timedelta, timezone
from dateutil import parser
from server_constants import DOTENV
from RecNetLogin.src.recnetlogin import RecNetLogin
import httpx

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


def get_headers_rnl(token) -> str:
    return {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }

def get_headers_official(token) -> str:
    return {
        'Cache-Control': 'no-cache',
        'Api-Version': 'v1',
        'Ocp-Apim-Subscription-Key': token
    }


def string_hash(input) -> str:
    result = -1  # Step 2: Initialize 'result' to -1

    def rotate_right(val, r_bits):
        val &= 0xFFFFFFFF  # Ensure it's within 32-bit range
        r_bits %= 32  # Ensure shift is within bounds
        rotated_val = ((val >> r_bits) | (val << (32 - r_bits))) & 0xFFFFFFFF  # Perform rotation

        # Convert to signed integer
        if rotated_val & (1 << (32 - 1)):  # If the sign bit is set
            rotated_val -= 1 << 32  # Subtract 2**32 to get the negative value

        return rotated_val

    for i in range(len(input)):  # Step 3: For each character in the string
        ascii_val = ord(input[i])  # Convert the character to its ASCII byte
        shift_count = (12*i + 7) % 32  # Ensure shift count is between 0 and 31
        rotated_val = rotate_right(ascii_val, shift_count)
        result ^= rotated_val  # Step 5: Bit xor with 'result'

    hex_str = hex(result & 0xFFFFFFFF)[2:] # Convert 'result' to hexadecimal
    hex_str = hex_str[:6] # Ensure the hexadecimal string is 6 digits long
    return hex_str  # Step 7: Return the hexadecimal string


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
    if token:
        headers = get_headers_official(token)
        endpoint = f"https://apim.rec.net/public/playerevents/{event_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
    else:
        rnl = RecNetLogin()
        token = rnl.get_token(include_bearer=True)
        headers = get_headers_rnl(token)
        endpoint = f"https://api.rec.net/api/playerevents/v1/{event_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
        rnl.close()

    if response.status_code // 100 == 2:
        return response.json()
    else:
        return None


async def get_next_event_by_player(player_id: int) -> int:
    token=DOTENV["RN_SUBSCRIPTION_KEY"]
    if token:
        headers = get_headers_official(token)
        endpoint = f"https://apim.rec.net/public/playerevents/creator/{player_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
    else:
        rnl = RecNetLogin()
        token = rnl.get_token(include_bearer=True)
        headers = get_headers_rnl(token)
        endpoint = f"https://api.rec.net/api/playerevents/v1/creator/{player_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
        rnl.close()

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