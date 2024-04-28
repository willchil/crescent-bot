from utility import parse_event_times
from utility import get_room_id
from server_constants import ROOM_DICTIONARY
import json

_MAIN_TEMPLATE = "nightclub"

KEY_NAME = "name"
KEY_DESCRIPTION = "description"
KEY_ROOM = "room"
KEY_START = "start"
KEY_DURATION = "duration"
KEY_ANNOUNCEMENT = "announcement"
KEY_ROOM_ID = "room_id"
KEY_START_DATE = "start_date"
KEY_END_DATE = "end_date"


def _read_template(filename):
    with open(f'event_templates/{filename}.json', 'r') as file:
        data = json.load(file)
    return data

async def process_with_defaults(dict):
    result = get_main_template()
    result.update(dict)
    return await process_settings(result)
    

async def process_settings(dict):
    (start, end, err) = parse_event_times(dict[KEY_START], dict[KEY_DURATION])
    if err:
        return (None, err)
    
    dict[KEY_START_DATE] = start
    dict[KEY_END_DATE] = end

    room_name = dict[KEY_ROOM].lower()
    if room_name in ROOM_DICTIONARY:
        dict[KEY_ROOM_ID] = ROOM_DICTIONARY[room_name]
    else:
        dict[KEY_ROOM_ID] = await get_room_id(room_name)

    return (dict, None)

def get_main_template():
    return _read_template(_MAIN_TEMPLATE)