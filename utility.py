from datetime import datetime, timedelta
import pytz


@staticmethod
def get_headers(token) -> str:
    return {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }


@staticmethod
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


@staticmethod
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
    
    hex_str = hex(result)[2:]  # Convert 'result' to hexadecimal
    hex_str = hex_str[:6]  # Ensure the hexadecimal string is 6 digits long
    return hex_str  # Step 7: Return the hexadecimal string