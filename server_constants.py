from dotenv import dotenv_values

DEBUG = False

CRESCENT_MEDIA = 1188116803814162522

EVENT_ROLE = 1188332286500933713
OWNER_ROLE = 1188119778611712040

BOT_CHANNEL = 1194502014244225164
REGISTRATION_CHANNEL = 1332580229482287134
EVENTS_CHANNEL = BOT_CHANNEL if DEBUG else 1188119118747013210

CRESCENT_REACTION = '<:crescent_1:1192293419557597316>'
DOTENV = dotenv_values(".env.secret")

ROOM_DICTIONARY = {
    "crescentnightclub": 25357294,
    "clubcrescent": 2002005,
    "recroombeachfest": 73827363,
    "crescentlounge": 14321703
}