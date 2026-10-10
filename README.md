# enako-bot

## what's this
My personal bot and the QQ integrated backend, for mahjong

## How to use
首次启动或升级前，先按下方说明准备 `group_config.json`；缺少文件将阻止机器人启动。

```bash
docker compose build
docker compose up -d
```
Other references to `docker-compose.yaml`

## environment
**.env.prod**

QQ adapter
```bash
BOT_ADAPTER=qq
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
onebot v11 adapter
```bash
BOT_ADAPTER=onebot11
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

## 插件群聊与私聊开关

`.env` 的 `ENABLED_PLUGINS` 决定进程加载哪些插件：不设置时加载当前适配器可用的全部业务插件，`[]` 不加载业务插件，指定列表只加载选中的插件。`_adapter`、`group_config` 始终加载，QQ 模式还加载 `qq_command_panel`；`group_config` 不能放入 `ENABLED_PLUGINS`。选中插件加载失败会阻止启动，即使该插件在所有群中都关闭，也必须满足其原有初始化配置要求。

群策略从 NoneBot 配置字段 `GROUP_CONFIG_FILE` 读取，默认 `plugin_data/group_config.json`。相对路径固定基于 `nonebot/bot.py` 所在目录，与启动工作目录无关；也可以填写绝对路径。

Docker 默认路径是 `/app/plugin_data/group_config.json`，使用已有卷对应宿主机 `/opt/bot-data/plugin_data/group_config.json`，无需新增挂载。发布前备份 `.env`，复制 [完整示例](docs/examples/group_config.json) 到宿主机该路径并替换实际群标识；若要保留当前全部响应行为，明确写入 `{}`。文件必须在新进程启动前存在，程序不会自动生成或修复配置。

```bash
GROUP_CONFIG_FILE=/app/plugin_data/group_config.json
```

顶层只允许实际发现的本地业务插件名称，目前为 `bot_assist`、`gsz-assist`、`mahjong-assist`、`hyw_assist`；已知但未加载的插件也可填写，群开关不能使它自动加载。每个插件必须完整填写三个字段：

```json
{
  "hyw_assist": {
    "default_enabled": false,
    "private_enabled": false,
    "groups": {
      "qq:实际群group_id": {"enabled": true},
      "onebot11:123456789": {"enabled": true}
    }
  }
}
```

- `default_enabled`：未列出的群是否允许响应。
- `private_enabled`：机器人私聊是否允许响应，与群开关独立。
- `groups`：群覆盖项，只允许必填的 `enabled`；显式群开关覆盖默认值。

未配置的业务插件保持原行为。布尔值只接受 `true` / `false`，不接受数字、字符串或 `null`。不接受额外字段，包括 `config`、`credential_ref`、`channel_enabled`，也没有 `version`、`defaults`、`plugins`、`$schema` 包裹层。基础插件和第三方依赖不能作为受控插件填写。参见 [Schema](docs/schemas/group_config.schema.json) 和 [升级方案](docs/group-config-upgrade-plan.md)。

群键格式只能是 `qq:<group_id>` 或 `onebot11:<group_id>`，区分大小写。QQ ID 是桥从实际群事件读取的 `group_id`，可从已有原始事件日志核对；不能用 `group_openid`、群名称或普通 QQ 群号代替。QQ 后缀长度 1～256，禁止空白和冒号。OneBot 后缀使用实际群号，只允许 ASCII 十进制数字，首位为 1～9，无前导零，长度 1～256。不同适配器的条目可以共存；同一进程的机器人账号共享策略。

配置须为可读取的普通文件，UTF-8 无 BOM、标准 JSON。缺失文件、空文件、重复键、注释、尾逗号、`NaN` / `Infinity`、未知字段和非法群键均导致启动失败；错误会指出文件及字段位置，不输出原始配置值。

修改 JSON 或 `.env` 后重启机器人生效；运行中的进程固定使用启动快照。Docker 服务环境变量改变后需重新创建服务以读取新环境。禁用响应器静默跳过，不发提示、不执行业务 handler，也不阻止后续响应器；启用响应器继续遵守原有规则、权限和阻断行为。QQ C2C 私聊受控，频道消息及频道私信沿用原行为。QQ 指令面板仍显示已加载的全局命令列表，执行时才判断群开关。

人数统计继续共享同一个摄像头、服务和忙碌锁，保留现有 `PEOPLE_COUNTER_*`；麻将 OCR 保留全局 `INPUT_IMG_SIZE`。群绑定数据库仍存原始群 ID，无需迁移。允许群可完成 `/识图牌理` 的等待图片流程，其他群或其他用户的图片不会完成该会话；重启会结束内存中的等待会话。

升级并重启后，请按方案第 10.2 节完成实际群消息、摄像头抓拍、模型推理及回复验收。出问题时回滚镜像及对应配置文件并重启，数据库无需反向迁移。

## tips
Some of the code references:
* https://github.com/dev-soragoto/simple-bot
