# crescent-bot
The official bot for the Crescent Media Discord server.

This project requires a `.env.secret` file in the root directory with the following format:

```
BOT_TOKEN={your_bot_token}
RN_SESSION_TOKEN={your_recnet_session_token}
RN_SUBSCRIPTION_KEY={your_recnet_subscription_key}
HASH_SALT={your_hash_salt}
```

`BOT_TOKEN` is the Discord token associated with your bot, and `HASH_SALT` is a cryptographic salt, applied before hashing the username in the `/register` command.

`RN_SESSION_TOKEN` is the token obtained by following the instructions from [RecNetLogin](https://github.com/Jegarde/RecNet-Login/). `RN_SUBSCRIPTION_KEY` is your subscription key for the official RecNet API, available through the [developer portal](http://devportal.rec.net). The official API is used for account lookups when possible, and the bot falls back to the RecNetLogin API if an official subscription key is not provided.