# enako-bot

## what's this
My personal bot and the QQ integrated backend, for using naga

## How to use
```bash
docker compose build
docker compose up -d
```
Other references to `docker-compose.yaml`

## environment

**.env.prod**

```bash
DRIVER=~websockets
LOG_LEVEL=DEBUG
ONEBOT_WS_URLS=["ws://napcat:3001"]
ONEBOT_ACCESS_TOKEN=
QQSHELL_ADMIN=[""]
QQSHELL_HOST=""
QQSHELL_PORT=22
QQSHELL_HOST_USER=""
QQSHELL_HOST_KEY_PATH="/app/id_rsa"
FEAK_SHELL_API_KEY=""
NAGA_ASSIST_ADMIN=[""]
NAGA_ASSIST_SERVER=""
NAGA_ASSIST_SECRET=""
REPEAT_THRESHOLD=3
REPEAT_CD=180
REPEAT_WHITE_LIST=[""]
```

## tips
Some of the code references:
* https://github.com/dev-soragoto/simple-bot

* https://github.com/yejue/nonebot-plugin-qqshell

auto-naga service:
* https://github.com/Diving-Fish/auto-naga
