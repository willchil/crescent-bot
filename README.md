# crescent-bot
The official bot for the Crescent Media Discord server.

This project requires a `.env.secret` file in the root directory with the following format:

```
BOT_TOKEN={your_bot_token}
VRCHAT_USERNAME={vrchat_username|email}
VRCHAT_PASSWORD={vrchat_password}
GITHUB_TOKEN={github_gist_token}
HASH_SALT={your_hash_salt}
```

`BOT_TOKEN` is the Discord token associated with your bot, and `HASH_SALT` is a cryptographic salt, applied before hashing the username in the `/register` command.