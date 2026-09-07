# OneBot v11 与 QQ 官方适配器统一维护方案

## 背景

当前项目存在两条适配器分支：

- `adapter-qq`：使用 `nonebot-adapter-qq`，当前工作区所在分支。
- OneBot v11 分支：使用 `nonebot-adapter-onebot` 的 OneBot v11 适配器。

这两条分支的业务目标一致，差异主要集中在 NoneBot 入口、依赖、环境变量、消息段构造、群聊事件、at 解析、图片发送等适配器相关代码。如果长期用两个功能分支分别维护，业务修复需要重复 cherry-pick，适配器差异也会逐渐混进业务逻辑，维护成本会越来越高。

建议改成“单主线 + 适配器兼容层”的维护方式：业务插件只依赖项目内部的适配器抽象，OneBot v11 和 QQ 官方适配器的差异集中在少数 adapter bridge 文件中。

## 推荐结论

建议保留一个长期主分支，例如 `main`，在同一套代码中同时支持两种适配器；不建议继续长期维护两个并行功能分支。

具体策略：

1. `main` 保存全部业务代码、模板、数据处理、渲染逻辑和测试。
2. `adapter-qq`、`adapter-onebot11` 不再作为长期开发分支，只作为迁移过渡或线上紧急回滚分支。
3. 适配器差异通过配置选择，例如 `BOT_ADAPTER=qq` 或 `BOT_ADAPTER=onebot11`。
4. 插件内禁止直接依赖具体适配器模块，例如 `nonebot.adapters.qq` 或 `nonebot.adapters.onebot.v11`。
5. 新业务功能只能合入主线；适配器专属代码只能放进项目约定的兼容层目录。

## 当前仓库中的主要耦合点

以当前 `adapter-qq` 分支为例，适配器耦合点主要有：

- `nonebot/bot.py`
  - 直接导入并注册 `nonebot.adapters.qq.Adapter`。
- `nonebot/pyproject.toml`
  - 依赖 `nonebot-adapter-qq`。
  - `[tool.nonebot].adapters` 固定为 QQ 官方适配器。
- `nonebot/requirements.txt`
  - 锁定 `nonebot-adapter-qq==1.7.1`。
- `nonebot/src/plugins/mahjong-assist/__init__.py`
  - 直接导入 `nonebot.adapters.qq.MessageSegment`、`MessageEvent`。
  - 使用 `MessageSegment.file_image(data=pic)`。
  - 从消息段中读取 `msg["image"]` 和 `data["url"]`。
- `nonebot/src/plugins/gsz-assist/__init__.py`
  - 直接导入 `nonebot.adapters.qq.Event`、`MessageSegment`、`GroupMessageCreateEvent`、`Message`。
  - 使用 `event.mentions` 解析 at。
  - 使用 `MessageSegment.mention_user(user_id)`。
  - 使用 `GroupMessageCreateEvent` 判断群聊。
  - 使用 `event.group_id`、`event.get_user_id()`。

这些地方应该从业务插件中剥离出去。

## 目标架构

建议新增一个项目内部兼容层，例如：

```text
nonebot/src/infrastructure_plugins/_adapter/
  __init__.py
  base.py
  qq.py
  onebot11.py
  runtime.py
```

职责划分：

- `base.py`
  - 定义业务插件需要的最小接口和数据结构。
- `qq.py`
  - 封装 QQ 官方适配器的事件判断、at 解析、图片消息构造。
- `onebot11.py`
  - 封装 OneBot v11 的事件判断、at 解析、图片消息构造。
- `runtime.py`
  - 根据配置选择当前适配器实现。
- 入口始终显式加载 `_adapter` 基础设施插件，不受业务插件白名单影响。
- QQ 模式额外显式加载 `src.infrastructure_plugins.qq_command_panel`；OneBot 模式不加载。命令面板不参与业务插件发现，不应列入 `ENABLED_PLUGINS`。
- 业务插件
  - 只导入 `infrastructure_plugins._adapter` 暴露的接口，不直接导入具体适配器。

## 兼容层接口建议

业务插件当前需要的能力不多，先不要设计过大的抽象。建议从下面这些接口开始：

```python
from typing import Any, Protocol

class AdapterBridge(Protocol):
    name: str

    def image_from_bytes(self, data: bytes) -> Any:
        """把图片 bytes 转成当前适配器可发送的消息段。"""

    def mention_user(self, user_id: str) -> Any:
        """构造 at 用户消息段。"""

    def get_user_id(self, event: Any) -> str:
        """获取发送者 ID。"""

    def is_group_event(self, event: Any) -> bool:
        """判断是否群聊事件。"""

    def get_group_id(self, event: Any) -> str | None:
        """获取群 ID；私聊或不支持群 ID 时返回 None。"""

    def get_mentioned_user_ids(self, event: Any) -> list[str]:
        """获取消息中被 at 的用户 ID。"""

    def extract_first_image_url(self, message: Any) -> str | None:
        """从消息中取第一张图片 URL。"""
```

注意事项：

- 返回值类型可以先用 `Any`，因为 NoneBot 不同适配器的消息段类型不同。
- 不要一开始追求完整消息抽象，只抽象业务确实使用的能力。
- 如果以后支持更多平台，再扩展这个接口。

## NoneBot 入口统一方式

建议把 `nonebot/bot.py` 改成按环境变量注册适配器：

```python
import os
import nonebot

nonebot.init()
driver = nonebot.get_driver()

adapter = os.getenv("BOT_ADAPTER", "qq").lower()

if adapter == "qq":
    from nonebot.adapters.qq import Adapter as QQAdapter
    driver.register_adapter(QQAdapter)
elif adapter == "onebot11":
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
    driver.register_adapter(OneBotV11Adapter)
else:
    raise RuntimeError(f"Unsupported BOT_ADAPTER: {adapter}")

nonebot.load_plugin("nonebot_plugin_htmlrender")
nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
```

这样可以保持一个入口文件，不再为适配器维护两份 `bot.py`。

## 依赖管理建议

短期最简单的做法是在同一个依赖文件中同时安装两个适配器：

```toml
dependencies = [
    "nonebot2[aiohttp,httpx]>=2.5.0",
    "nonebot-adapter-qq>=1.7.1",
    "nonebot-adapter-onebot>=2.4.0",
]
```

优点：

- Docker 镜像、部署脚本、开发环境简单。
- 切换适配器只需要改环境变量。
- CI 可以同时检查两种入口是否能导入。

缺点：

- 镜像会多一点依赖体积。
- 两个适配器的依赖升级可能互相影响。

如果之后依赖冲突明显，再改成 extras：

```toml
[project.optional-dependencies]
qq = ["nonebot-adapter-qq>=1.7.1"]
onebot11 = ["nonebot-adapter-onebot>=2.4.0"]
all = [
    "nonebot-adapter-qq>=1.7.1",
    "nonebot-adapter-onebot>=2.4.0",
]
```

当前项目规模下，建议先采用“默认同时安装两个适配器”的方式，减少维护复杂度。

## 配置文件建议

建议把适配器选择和适配器认证配置分开：

```bash
BOT_ADAPTER=qq
DRIVER=~aiohttp
```

QQ 官方适配器继续使用：

```bash
QQ_BOTS='[...]'
```

OneBot v11 按实际连接方式配置，例如反向 WebSocket 或 HTTP：

```bash
BOT_ADAPTER=onebot11
ONEBOT_ACCESS_TOKEN=xxx
```

实际变量名以 NoneBot 和对应适配器文档为准，但项目内统一使用 `BOT_ADAPTER` 决定加载哪个适配器。

## 插件改造建议

### `mahjong-assist`

当前插件里适配器相关的逻辑主要是：

- 图片消息发送：`MessageSegment.file_image(data=pic)`。
- 等待图片消息后读取图片 URL：`msg["image"][0].data["url"]`。
- 等待事件类型：`MessageEvent`。

建议改成：

```python
from src.infrastructure_plugins._adapter import bridge

message = bridge.image_from_bytes(pic)
url = bridge.extract_first_image_url(resp.get_message())
```

等待事件的类型注解可以先放宽为 `Any`，减少对具体适配器事件类的依赖。

### `gsz-assist`

当前插件里适配器相关的逻辑主要是：

- 群聊事件判断：`isinstance(event, GroupMessageCreateEvent)`。
- at 列表：`event.mentions`。
- at 消息段：`MessageSegment.mention_user(user_id)`。
- 群 ID：`event.group_id`。
- 用户 ID：`event.get_user_id()`。

建议改成：

```python
from src.infrastructure_plugins._adapter import bridge

if bridge.is_group_event(event):
    at_list = bridge.get_mentioned_user_ids(event)

group_id = bridge.get_group_id(event)
user_id = bridge.get_user_id(event)
message = bridge.image_from_bytes(pic)
```

绑定雀庄和排行榜这类必须依赖群 ID 的命令，应显式处理非群聊情况：

```python
group_id = bridge.get_group_id(event)
if group_id is None:
    await matcher.finish("该命令只能在群聊中使用", at_sender=True)
```

## 分支策略

建议采用下面的分支模型：

- `main`
  - 唯一长期维护分支。
  - 同时支持 QQ 官方适配器和 OneBot v11。
- `adapter-qq`
  - 迁移完成后停止常规开发。
  - 只用于线上回滚或比较历史实现。
- `adapter-onebot11`
  - 迁移完成后停止常规开发。
  - 只用于线上回滚或比较历史实现。
- `feature/*`
  - 新功能开发分支，必须从 `main` 拉出。
- `fix/*`
  - Bug 修复分支，必须从 `main` 拉出。

合并规则：

1. 业务功能不允许只合入某个适配器分支。
2. 适配器专属改动必须限制在 `_adapter` 兼容层、入口注册、依赖和部署配置中。
3. 如果线上仍然暂时部署旧分支，修复也应先合入 `main`，再按需 cherry-pick 到旧分支。

## 推荐迁移步骤

### 第 1 步：冻结两个旧分支的业务开发

在迁移期间，不再分别向两个适配器分支添加新业务功能。必要 bug 修复先记录，再统一合入主线。

### 第 2 步：选定主线基准

建议选择当前业务更完整、线上更接近生产的分支作为基准。根据当前仓库状态，`adapter-qq` 已包含最新的模板渲染、排行榜、图片发送等修复，可以优先作为统一主线的起点。

### 第 3 步：从另一个分支提取差异

从 OneBot v11 分支中提取以下内容：

- OneBot v11 的依赖和配置。
- OneBot v11 的 `bot.py` 注册方式。
- OneBot v11 的消息段构造方式。
- OneBot v11 的 at 解析方式。
- OneBot v11 的群聊事件和群 ID 获取方式。
- OneBot v11 的图片 URL 读取方式。

只迁移适配器差异，不把已经在 `adapter-qq` 中修复过的业务代码覆盖回去。

### 第 4 步：新增 `_adapter` 兼容层

先实现 QQ 官方适配器版本，保证当前行为不变；再实现 OneBot v11 版本。

这个顺序风险更低，因为当前工作区就是 `adapter-qq`，可以先把现有逻辑搬进兼容层，再改插件调用点。

### 第 5 步：改插件调用点

优先改造适配器耦合最明显的文件：

1. `nonebot/src/plugins/gsz-assist/__init__.py`
2. `nonebot/src/plugins/mahjong-assist/__init__.py`
3. `nonebot/bot.py`
4. `nonebot/pyproject.toml`
5. `nonebot/requirements.txt`

每改完一个插件，都要确认不再直接导入具体适配器：

```bash
rg "nonebot\\.adapters\\.(qq|onebot)" nonebot/src/plugins
```

### 第 6 步：补最小测试或检查脚本

建议至少提供下面两个检查命令：

```bash
BOT_ADAPTER=qq python -m nonebot
BOT_ADAPTER=onebot11 python -m nonebot
```

如果项目启动方式固定为 `python bot.py`，则在 `nonebot` 目录下执行：

```bash
BOT_ADAPTER=qq python bot.py
BOT_ADAPTER=onebot11 python bot.py
```

还可以补一个轻量导入检查脚本，验证两个 bridge 都能导入：

```bash
python -c "from src.infrastructure_plugins._adapter.qq import bridge"
python -c "from src.infrastructure_plugins._adapter.onebot11 import bridge"
```

### 第 7 步：部署双环境验证

建议同时保留两份 `.env`：

```text
.env.qq
.env.onebot11
```

验证清单：

- Bot 能启动。
- `/日麻小助手` 返回帮助。
- `/牌理` 能返回图片。
- `/识图牌理` 能读取图片并返回结果。
- `/公式战绑定` 能绑定用户。
- `/吃鱼` 能按自己、用户名、at 用户查询。
- `/仇恨榜` 和 `/好人榜` 能按自己、用户名、at 用户查询。
- `/雀庄绑定` 只能在群聊中使用。
- `/排行榜` 能读取群绑定并返回图片。

## 代码边界约定

建议在项目里明确以下规则：

- 插件业务代码不得导入 `nonebot.adapters.qq`。
- 插件业务代码不得导入 `nonebot.adapters.onebot.v11`。
- 具体适配器导入只能出现在：
  - `nonebot/bot.py`
  - `nonebot/src/infrastructure_plugins/_adapter/qq.py`
  - `nonebot/src/infrastructure_plugins/_adapter/onebot11.py`
- 服务层，例如 `service.py`、`ratedata_manage.py`、`userdata_manage.py`，不得依赖 NoneBot 事件类型或消息段。
- 图片渲染、OCR、数据读写、API 请求应保持完全适配器无关。

可以用下面命令定期检查：

```bash
rg "nonebot\\.adapters\\.(qq|onebot)" nonebot/src/plugins
```

如果有输出，就说明业务插件又直接依赖了具体适配器。

## 风险点与处理建议

### at 解析差异

QQ 官方适配器中当前使用 `event.mentions`。OneBot v11 通常需要从消息段中读取 `type == "at"` 的 segment。这个差异必须放进 bridge 中，不要散落在命令处理函数里。

### 图片发送差异

QQ 官方适配器当前使用 `MessageSegment.file_image(data=pic)`。OneBot v11 常见写法可能是 `MessageSegment.image(pic)`、文件路径、URL 或 base64，具体取决于适配器版本和协议端支持。建议 bridge 提供 `image_from_bytes`，内部按适配器实现。

### 群聊事件差异

QQ 官方适配器当前用 `GroupMessageCreateEvent`。OneBot v11 常见是 `GroupMessageEvent`。业务代码只应该调用 `bridge.is_group_event(event)`。

### 群 ID 差异

当前代码直接访问 `event.group_id`。不同适配器的字段类型可能是 `int` 或 `str`。bridge 应统一返回 `str | None`，数据层统一使用字符串作为 key。

### 图片 URL 获取差异

当前代码从 `msg["image"][0].data["url"]` 取 URL。OneBot v11 的图片 segment 字段可能是 `url`、`file` 或其他协议端字段。bridge 应统一提供 `extract_first_image_url`；如果某个协议端只能拿到 file id，则由 bridge 或服务层进一步下载/转换。

## 建议的落地优先级

优先级从高到低：

1. 新增 `_adapter` 兼容层，并先封装当前 QQ 官方适配器行为。
2. 改造 `gsz-assist` 和 `mahjong-assist`，移除业务插件中的具体适配器导入。
3. 改造 `bot.py`，通过 `BOT_ADAPTER` 注册适配器。
4. 合并依赖，保证两种适配器都可安装。
5. 从 OneBot v11 分支迁移 bridge 实现。
6. 增加启动检查和 rg 检查。
7. 冻结旧适配器分支，后续只维护 `main`。

## 最终建议

这个项目不需要拆成两个仓库，也不适合长期维护两个功能分支。最稳妥的方式是在一个主线里保留两套“适配器边缘代码”，让业务插件、服务层、模板渲染和数据逻辑完全共用。

短期可以接受两个适配器都安装在同一个环境里，先把维护复杂度降下来。等项目规模变大或依赖冲突出现后，再把依赖拆成 optional extras。真正需要严格隔离的是代码边界，而不是 Git 分支。
