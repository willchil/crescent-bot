from utility import parse_event_times
from server_constants import ROOM_DICTIONARY
import json

_MAIN_TEMPLATE = "main"

KEY_NAME = "name"
KEY_DESCRIPTION = "description"
KEY_ROOM = "room"
KEY_START = "start"
KEY_DURATION = "duration"
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

    room_id = dict[KEY_ROOM].lower()
    if room_id in ROOM_DICTIONARY:
        dict[KEY_ROOM_ID] = ROOM_DICTIONARY[room_id]
    else:
        dict[KEY_ROOM_ID] = 0 # TODO: Do an async RecNet call to get the id

    return (dict, None)

def get_main_template():
    return _read_template(_MAIN_TEMPLATE)