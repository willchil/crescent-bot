import httpx
import pytz

async def create_event(token, start_time, end_time) -> (bool, str):

    EVENT_ENDPOINT = "https://api.rec.net/api/playerevents/v2"

    # Convert both times to the GMT time zone
    gmt_timezone = pytz.timezone('GMT')
    start_time_gmt = start_time.astimezone(gmt_timezone)
    end_time_gmt = end_time.astimezone(gmt_timezone)

    # Format as "EEE, DD MMM YYYY HH:MM:SS GMT"
    start_time_str = start_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    end_time_str = end_time_gmt.strftime("%a, %d %b %Y %H:%M:%S GMT")

    payload = {
        "Name": "Party @ Crescent Nightclub",
        "Description": "Come party with us at Crescent Nightclub, one of Rec Room's most prestigious nightclubs.",
        "RoomId": "25357294",
        "StartTime": start_time_str,
        "EndTime": end_time_str,
        "Accessibility": "0"
    }

    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # Uncomment for testing:
    #return (True, "https://rec.net/event/8410541010311578971")

    async with httpx.AsyncClient() as client:
        response = await client.post(EVENT_ENDPOINT, data=payload, headers=headers)

    # Check if the request was successful (status code 2xx)
    if response.status_code // 100 == 2:
        eventLink = "https://rec.net/event/" + response.json()["PlayerEvent"]["PlayerEventId"]
        return (True, eventLink)
    else:
        return (False, f"{response}")