from datetime import datetime, timedelta
import pytz


def get_headers(token) -> str:
    return {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }


def get_event_times(start_hour, duration) -> (datetime, datetime):

    # Get the current time in the Pacific time zone
    pacific_timezone = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific_timezone)

    # Set a date offset if next time is not until tomorrow
    day_offset = 1 if current_time.hour >= start_hour else 0

    # Calculate the next time it's the start hour
    start_time = current_time.replace(hour=start_hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)

    # Calculate the end time
    end_time = start_time + timedelta(hours=duration)

    return (start_time, end_time)


def string_hash(input) -> str:
    hashcode = abs(hash(input)) % (10 ** 6)
    return str(hashcode)