import httpx
import pytz
from datetime import datetime, timedelta
from RecNetLogin.recnetlogin import RecNetLogin

async def create_event(token) -> str:

    EVENT_ENDPOINT = "https://api.rec.net/api/playerevents/v2"

    def get_event_times():
        # Get the current time in the Pacific time zone
        pacific_timezone = pytz.timezone('America/Los_Angeles')
        current_time = datetime.now(pacific_timezone)

        # Calculate days until the next Friday
        days_until_friday = (4 - current_time.weekday()) % 7
        if current_time.hour > 22:
            days_until_friday += 7

        # Calculate the next Friday at 10:00 PM
        start_time = current_time.replace(hour=22, minute=0, second=0, microsecond=0) + timedelta(days=days_until_friday)

        # Calculate the end time (2 hours later)
        end_time = start_time + timedelta(hours=2)

        # Convert both times to the GMT time zone
        gmt_timezone = pytz.timezone('GMT')
        start_time_gmt = start_time.astimezone(gmt_timezone)
        end_time_gmt = end_time.astimezone(gmt_timezone)

        # Format as "EEE, DD MMM YYYY HH:MM:SS GMT"
        start_time_str = start_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = end_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")

        return start_time_str, end_time_str

    start_time, end_time = get_event_times()

    payload = {
        "Name": "Party @ Crescent Nightclub",
        "Description": "Come party with us at Crescent Nightclub, one of Rec Room's most prestigious nightclubs.",
        "RoomId": "25357294",
        "StartTime": start_time,
        "EndTime": end_time,
        "Accessibility": "0"
    }

    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    #return "Test complete."

    async with httpx.AsyncClient() as client:
        response = await client.post(EVENT_ENDPOINT, data=payload, headers=headers)

    # Check if the request was successful (status code 2xx)
    if response.status_code // 100 == 2:
        return "Event created!"
    else:
        return f"Error creating event:\n{response}"


async def test_create_event():
    rnl = RecNetLogin()
    token = rnl.get_token(include_bearer=True)
    result = await create_event(token)
    print(result)
    rnl.close()

import asyncio
#asyncio.run(test_create_event())