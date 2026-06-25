# enako-bot

## what's this
My personal bot and the QQ integrated backend, for mahjong

## How to use
```bash
docker compose build
docker compose up -d
```
Other references to `docker-compose.yaml`

## environment

**.env.prod**

```bash
DRIVER=~aiohttp
QQ_BOTS='
[
  {
    "id": "xxx",
    "token": "xxx",
    "secret": "xxx",
    "intent": {
        "guild_members": true,
        "guild_messages": true,
        "guild_message_reactions": true,
        "direct_message": true,
        "c2c_group_at_messages": true,
        "interaction": true,
        "at_messages": true
    }
  }
]
'
INPUT_IMG_SIZE=1280

```

## tips
Some of the code references:
* https://github.com/dev-soragoto/simple-bot
