# 插件分群开关升级方案

## 1. 已确认的范围

本文件是本次升级的实施约定，示例及 Schema 均属于待实现的配置格式，当前机器人尚未读取它们。

用户已确认：

1. 本次只增加插件的群开关，人数统计继续使用一个摄像头。
2. 修改 JSON 或 `.env` 后，重启机器人生效。
3. 未启用时静默跳过响应器，让其他插件继续处理消息。
4. 麻将 OCR 尺寸继续使用全局 `INPUT_IMG_SIZE`。
5. 实际使用场景是 QQ 群和机器人私聊，不包含 QQ 频道及频道私信。

因此，本期 JSON 不包含插件业务参数：前面讨论过的 `config`、`credential_ref`、摄像头设备和区域文件字段均不进入本期格式，传入这些字段必须报错。摄像头继续使用现有 `PEOPLE_COUNTER_*` 环境配置；不新增 `PEOPLE_COUNTER_CREDENTIALS`，也不迁移现有密钥。

本期不增加群内管理命令、热更新、配置数据库、多摄像头服务、按群 OCR 模型或按群 QQ 指令面板。将来增加这些功能时，需另行修改字段约定和 Schema，不能提前接受并忽略未知字段。

## 2. 总体结构与职责

沿用现有插件发现和适配桥，增加一个基础插件 `group_config`：

```text
nonebot/
├── bot.py
└── src/infrastructure_plugins/
    ├── _adapter/
    ├── group_config/
    │   ├── __init__.py   # 注册运行预处理器，导出初始化入口
    │   ├── config.py     # 文件路径配置、严格字段模型、文件读取与校验
    │   └── service.py    # 启动快照、插件归属解析、开关判断
    └── qq_command_panel/
```

| 配置或组件 | 唯一职责 |
|---|---|
| `.env` 中的 `ENABLED_PLUGINS` | 决定当前进程加载哪些插件，保持现有选择语义 |
| `group_config.json` | 决定已加载的本地业务插件能否在某个群或机器人私聊中响应 |
| `group_config` 基础插件 | 读取一次配置，校验并统一执行开关判断 |
| `_adapter` | 判断群聊/机器人私聊，并提供群 ID |
| 业务插件 | 保留原有命令、权限、服务、业务参数及数据库 |

有效响应必须同时满足：插件已加载、场景开关允许、原有响应器规则和权限允许。群开关不赋予管理员权限，也不改变原有命令匹配规则。

`group_config` 随基础插件始终加载，顺序为 `_adapter`、`group_config`，QQ 模式再加载 `qq_command_panel`。它不能放入 `ENABLED_PLUGINS`，也不能作为 JSON 中的受控插件。

## 3. 文件位置与读取规则

新增唯一环境字段：

| 字段 | 类型 | 默认值 | 约束 |
|---|---|---|---|
| `GROUP_CONFIG_FILE` | 文件路径字符串，解析后为 `Path` | `plugin_data/group_config.json` | 不能为空或全为空白；允许绝对路径或相对路径 |

约定：

- 通过 NoneBot 的 `get_plugin_config()` 读取 `GROUP_CONFIG_FILE`；不另行读取 dotenv 或 `os.environ`。
- 相对路径基于 `nonebot/bot.py` 所在的项目目录，不能基于进程当前工作目录。在 `group_config/config.py` 中，以 `Path(__file__).resolve().parents[3]` 确定这个目录。
- Docker 默认实际路径为 `/app/plugin_data/group_config.json`，对应已有挂载中的宿主机 `/opt/bot-data/plugin_data/group_config.json`；不需要新增卷。
- 文件必须是可读取的普通文件，采用 UTF-8、无 BOM、标准 JSON；不允许注释、尾逗号、`NaN` 或 `Infinity`。
- 所有层级的重复 JSON 键都必须拒绝，不采用“后者覆盖前者”。读取器使用 `object_pairs_hook` 检测重复键，使用 `parse_constant` 拒绝非标准数值。
- 文件缺失、无权限、内容错误或路径指向目录时，启动失败。不自动创建文件，不把读取失败解释成全部启用。
- 文件只在启动阶段读取一次。修改或删除文件不会改变已启动进程的开关，重启后重新校验。
- 空对象 `{}` 是明确合法的配置，表示没有为任何插件设置场景限制。空文件不合法。

## 4. JSON 字段契约

完整示例见 [examples/group_config.json](examples/group_config.json)，结构约束见 [schemas/group_config.schema.json](schemas/group_config.schema.json)。实现以本节的字段及语义为准；Schema 补充机器可读的结构约束。

### 4.1 顶层

顶层是 `object`，键是本地业务插件的实际发现名称，值是 `PluginPolicy`。

当前有效名称为：`bot_assist`、`gsz-assist`、`mahjong-assist`、`hyw_assist`。名称区分大小写，不使用插件中文展示名称、模块完整路径或别名。

有效名称集合直接复用 `bot.py` 对 `src/plugins` 和 `src/qq_plugins` 的发现结果；不维护第二份运行时插件白名单。已知但当前全局未加载、或当前适配器不可用的本地业务插件可以出现在文件中，仍需完成全部格式校验。

以下名称不能写入：`_adapter`、`group_config`、`qq_command_panel`、`nonebot_plugin_htmlrender`、`nonebot_plugin_waiter`。基础插件和第三方依赖不参与场景开关。

没有顶层 `version`、`defaults`、`plugins` 或 `$schema` 字段。JSON Schema 只验证通用结构，是否为已知本地业务插件由启动校验补充检查。

### 4.2 `PluginPolicy`

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `default_enabled` | 严格布尔值 | 是 | 没有出现在 `groups` 中的群是否允许响应 |
| `private_enabled` | 严格布尔值 | 是 | 机器人私聊是否允许响应，独立于群开关 |
| `groups` | `object<string, GroupOverride>` | 是 | 具体群的开关覆盖，允许为空对象 |

除这三个字段外，不接受任何其他字段；字段不可为 `null`。布尔值只接受 JSON 的 `true`/`false`，拒绝 `0`、`1`、`"true"`、`"false"`。

### 4.3 `GroupOverride`

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `enabled` | 严格布尔值 | 是 | 替换该群的 `default_enabled` |

只接受 `enabled`，不接受 `config` 等额外字段。群条目即使设置为 `false`，也必须完整通过校验。

### 4.4 群键

唯一格式为 `<adapter>:<group_id>`，例如 `qq:group_a`、`onebot11:123456789`。

| 部分 | 约束 |
|---|---|
| `adapter` | 只接受小写 `qq` 或 `onebot11`；不接受适配器配置别名 |
| QQ 的 `group_id` | 长度 1～256 个字符；不包含空白字符或冒号；其余内容作为不透明字符串原样比较 |
| OneBot 的 `group_id` | 长度 1～256 个字符；只允许十进制 ASCII 数字，首位为 1～9，不能带前导零 |

运行时群键必须由 `f"{bridge.name}:{bridge.get_group_id(event)}"` 生成。不得根据群名查找，不进行大小写转换、去空白或其他猜测性归一化。运行时及读取器使用 `re.fullmatch()` 验证完整群键，不能使用只检查前缀的 `re.match()`。

QQ 模式继续使用当前桥返回的 `event.group_id`，不能改成 `group_openid`，也不能直接填写普通 QQ 群号。两字段不同时，必须以 `group_id` 为准。OneBot 使用当前桥对数字 `event.group_id` 的字符串转换结果。

不同适配器的条目可以共存在同一文件；运行时只查询当前适配器前缀。这个格式不区分同一适配器下的机器人账号：同一进程共享一份策略，不新增账号维度。

对于运行时的群聊事件，群 ID 缺失或不满足以上约束时，记录包含插件名和错误原因的日志并跳过该响应器，不能把它当成私聊或未配置群。此检查只适用于实际参与控制的业务响应器。

## 5. 完整示例及其确定行为

```json
{
  "hyw_assist": {
    "default_enabled": false,
    "private_enabled": false,
    "groups": {
      "qq:group_a": {"enabled": true},
      "qq:group_b": {"enabled": true},
      "qq:group_c": {"enabled": false},
      "onebot11:123456789": {"enabled": true}
    }
  },
  "mahjong-assist": {
    "default_enabled": true,
    "private_enabled": true,
    "groups": {
      "qq:group_b": {"enabled": false}
    }
  },
  "gsz-assist": {
    "default_enabled": true,
    "private_enabled": true,
    "groups": {
      "qq:group_c": {"enabled": false}
    }
  },
  "bot_assist": {
    "default_enabled": true,
    "private_enabled": true,
    "groups": {}
  }
}
```

示例中的群标识是占位符，部署前替换成桥实际返回的值。

| 场景 | 人数统计 | 麻将工具 | 公式战 | `enako` 检查 |
|---|---|---|---|---|
| QQ A 群 | 允许 | 允许 | 允许 | 允许 |
| QQ B 群 | 允许 | 禁止 | 允许 | 允许 |
| QQ C 群 | 禁止 | 允许 | 禁止 | 允许 |
| 未列出的 QQ 群 | 禁止 | 允许 | 允许 | 允许 |
| 机器人私聊 | 禁止 | 允许 | 允许 | 允许 |
| OneBot `123456789` 群 | 允许 | 允许 | 允许 | 允许 |

“允许”仍需通过原有命令规则和权限。人数统计在所有允许群中查询同一个现有摄像头，并共享原有服务和忙碌锁；A、B 群不能据此查询不同门店的摄像头。

## 6. 判断规则与边界

按下列顺序执行一次统一判断：

1. 判断响应器是否属于当前受控的本地业务插件；基础插件、第三方依赖及无业务归属的响应器直接沿用原有行为。
2. 事件不是消息事件时，沿用原有行为。本期只控制群消息及机器人私聊消息。
3. 业务插件没有出现在配置顶层时，沿用原有行为。这是明确的配置语义，不是读取失败后的降级。
4. 群消息：验证群 ID；优先使用 `groups[group_key].enabled`，没有群条目时使用 `default_enabled`。
5. 机器人私聊消息：使用 `private_enabled`。
6. QQ 频道消息、频道私信及其他不在本期范围的消息沿用原有行为，不读取 `private_enabled`，不提供 `channel_enabled` 字段。

禁止时：

- 在 `run_preprocessor` 中抛出 `IgnoredException("plugin disabled for this conversation")`，取消当前响应器。
- 不发送提示，不调用该插件 handler，不访问其业务 API 或写入业务数据库。
- 不抛出 `StopPropagation`，不改写响应器的 `block`、`rule` 或 `permission`。
- 后续响应器继续按 NoneBot 原有优先级运行。只保证当前禁用响应器不会阻断传播，其他启用响应器仍可以按原有 `block=True` 阻断传播。

当前本地 NoneBot 的运行流程在预处理取消后直接返回，早于 handler 和 `block` 的执行，因此上述行为可使用一个统一预处理器实现。实现时必须通过真实 `handle_event` 分发测试固定这项行为。

仅限制消息响应不等于卸载插件。全部群都关闭时，已加载插件仍会初始化现有服务，仍需满足原有全局配置要求。要停止加载人数统计插件，应调整 `ENABLED_PLUGINS`。

## 7. 模型、初始化与内部接口

### 7.1 配置模型

使用现有 Pydantic，不增加配置解析依赖：

- `GroupOverride`：仅包含必填严格布尔值 `enabled`。
- `PluginPolicy`：仅包含必填严格布尔值 `default_enabled`、`private_enabled`，以及必填 `dict[str, GroupOverride]` 类型的 `groups`。
- 顶层使用 `TypeAdapter(dict[str, PluginPolicy])` 校验解析后的 JSON 对象；不得增加包裹层。
- 两个字段模型都设置 `extra="forbid"` 和严格校验；字典键另外按第 4 节校验。
- 初始化校验全部条目，包括未加载插件、非当前适配器群及禁用群。
- 发布的运行时快照只保存只读映射及不可变值，不暴露可修改的字典，不在 handler 中写配置。

### 7.2 内部接口

```python
def initialize_group_config(
    *,
    known_business_plugins: frozenset[str],
    managed_business_plugins: frozenset[str],
) -> None: ...

def is_enabled(
    plugin_name: str,
    *,
    scope: Literal["group", "private"],
    group_key: str | None,
) -> bool: ...
```

接口契约：

- `known_business_plugins` 是两个本地业务目录发现名称的并集，不含渲染库及基础插件。
- `managed_business_plugins` 是本次适配器下经过全局加载选择的本地业务插件集合。
- `managed_business_plugins` 必须是 `known_business_plugins` 的子集，否则初始化失败。
- `initialize_group_config` 在进程启动时调用且只调用一次；重复调用是程序错误，抛出 `RuntimeError`，不实现隐式重载。
- 初始化失败抛出 `RuntimeError`，附带文件路径和字段路径，不能输出摄像头密钥、机器人凭据、完整环境配置或原始消息。格式校验日志只输出错误类型及位置；Pydantic 错误使用 `errors(include_input=False)` 提取，不能直接打印含原始输入的异常或整个 JSON。
- `is_enabled` 只能在初始化后调用，未初始化调用抛出 `RuntimeError`。
- 群场景的 `group_key` 必须是合法非空群键；私聊场景的 `group_key` 必须为 `None`；违背调用约定抛出 `ValueError`，不是配置缺省。
- 非受控插件及非本期消息场景在预处理器中排除，不传入 `is_enabled`。
- `is_enabled` 的 `plugin_name` 必须属于受控集合，`scope` 必须为 `group` 或 `private`，否则抛出 `ValueError`。
- 受控但未配置的插件返回 `True`；已配置插件严格执行第 6 节的字段选择规则。

### 7.3 启动次序

1. `nonebot.init()`，注册现有适配器。
2. 加载基础插件，包括 `_adapter` 和 `group_config`；基础插件加载返回 `None` 时继续使用现有的显式失败机制。
3. 在现有业务加载函数中复用 `_discover_plugins()` 得到已知集合、当前适配器可用集合及 `ENABLED_PLUGINS` 选择结果。不得再扫描并维护另一套加载路径。`ENABLED_PLUGINS` 包含 `group_config` 时显式报错，不能因现有未知名称校验排除了基础插件名称而放行。
4. 直接调用 `initialize_group_config()`，完成文件、类型、插件名称和群键校验并发布启动快照；调用放在 `bot.py` 的正常执行路径，不能只放在插件导入内部而被 NoneBot 的插件加载错误处理吞掉。
5. 沿用现有路径加载选中的业务插件。对选中的插件，`nonebot.load_plugin()` 返回 `None` 时显式抛出 `RuntimeError`，避免启动了缺少选定业务插件的进程。
6. 启动机器人。无效的群配置必须在连接 QQ、同步指令面板、接收消息前使进程以非零状态退出。

第 5 步会把现有业务加载失败后继续运行的情况改成启动失败。启动测试需要提供合法的虚拟摄像头配置，或明确选择不含人数统计的业务插件，不能靠插件加载失败来通过测试。

### 7.4 响应器归属

使用 `matcher.plugin` 及其 `parent_plugin` 链，选择最接近响应器且在 `managed_business_plugins` 中的业务插件名称。没有这样的归属时，不施加本期限制；不根据模块名称字符串前缀猜测归属。

一个插件的所有响应器一起受控，包括命令、别名、关键词、帮助消息以及具备该业务归属的临时响应器。第三方 waiter 自己创建的响应器不新增业务开关，其会话仍受原有 `keep_session=True` 限制。

由于配置在进程内固定，已经在允许群发起的“识图牌理”会话可以正常等待同一会话中的图片；禁止群不得发起会话。重启会结束内存中的等待会话，不恢复或迁移会话。

## 8. 适配桥的最小改造

在 `AdapterBridge` 增加唯一方法：

```python
def is_private_event(self, event: Any) -> bool: ...
```

| 适配器 | 群消息识别 | 机器人私聊识别 |
|---|---|---|
| QQ | 复用现有 `GroupMessageCreateEvent` 判断，包含其 @ 消息子类 | `C2CMessageCreateEvent` |
| OneBot v11 | 复用现有 `GroupMessageEvent` 判断 | `PrivateMessageEvent` |

QQ 的 `DirectMessageCreateEvent` 是频道私信，不能判成机器人私聊。不得使用 `not is_group_event(event)` 作为私聊判据。保留现有 `get_group_id()` 的返回语义，公式战数据库继续存原有群 ID，不添加适配器前缀、不迁移数据、不双写。

## 9. 文件修改清单

| 文件 | 具体修改 |
|---|---|
| `nonebot/bot.py` | 注册新基础插件；复用发现和选择结果初始化群配置；检查选中业务插件加载失败 |
| `nonebot/src/infrastructure_plugins/group_config/` | 实现第 3～7 节的模型、读取器、快照和唯一预处理器 |
| `_adapter/base.py`、`qq.py`、`onebot11.py` | 增加并实现 `is_private_event()` |
| `nonebot/tests/test_group_config.py` | 文件、模型、名称、群键、快照和判断规则测试 |
| `nonebot/tests/test_group_config_dispatch.py` | 两种适配器的 NoneBot 分发、阻断行为、会话及业务副作用测试 |
| `nonebot/tests/test_bot_plugin_loading.py` | 显式写入临时配置文件；更新基础插件集合及失败启动用例 |
| `nonebot/tests/test_qq_bridge.py` 等适配测试 | 补充机器人私聊/频道私信边界及群键来源测试 |
| `README.md` | 增加配置位置、字段规则、群标识填写方式和重启生效说明 |

人数统计的服务、摄像头配置、忙碌锁、推理及关闭流程保持现有单摄像头实现；麻将服务及 `INPUT_IMG_SIZE` 保持全局实现。业务 handler 不增加各自的白名单判断。依赖文件、Docker 挂载和现有数据库无需调整。

QQ 指令面板继续同步已加载命令的全局列表：本期不保证禁用群的面板隐藏指令，执行时统一开关仍会静默跳过。这是确定的界面限制，不能把面板可见性当作启用判断。

## 10. 实施阶段与验收

### 阶段一：严格配置与初始化

实现读取器、模型、群键规则、名称校验和启动快照；复用入口的插件发现结果。验收：所有合法示例可加载，所有错误条目都能定位并阻止启动，包括非当前适配器及未加载插件的错误条目。

### 阶段二：统一分发控制

实现适配桥私聊判断与预处理器；验收：禁用响应器不执行 handler、不阻断后续响应器，启用响应器保持原有规则和权限。禁止群不能发起识图会话，允许会话不会消费其他群的图片。

### 阶段三：回归与部署

更新已有启动测试、运行原有插件测试、检查两个适配器的完整链路、补充 README。上线前完成下列真实场景验收；没有实际验证的项目标为未完成，不能用 mock 成功替代真实场景成功。

### 10.1 自动化用例矩阵

| 范围 | 必测场景 |
|---|---|
| 文件读取 | 默认路径、显式绝对路径、与 CWD 无关的相对路径、缺失、目录、无权限、空文件、UTF-8 错误、BOM、非法 JSON、重复键、非标准数值 |
| 字段 | 顶层非对象；三个必填字段分别缺失；群条目缺 `enabled`；各层未知字段；`null`；字符串/数字冒充布尔值；`groups` 非对象；合法空对象 |
| 名称 | 四个业务名称；未知名称；错误大小写；中文名称；基础插件；第三方依赖；已知但全局未加载插件 |
| 群键 | QQ 不透明标识；`group_id` 与 `group_openid` 不同；两适配器同后缀不混淆；错误前缀；空后缀；空白；额外冒号；超长 ID；OneBot 前导零及非数字 |
| 判断 | 未配置插件；未配置群的两个默认值；显式开和关；显式覆盖默认；私聊两个值；非当前适配器条目；非法接口调用；重复初始化；未初始化调用 |
| 分发 | 禁用 `block=True` 响应器后，后续业务响应器确实执行；启用后保持原阻断行为；帮助/关键词/别名一起受控；权限拒绝仍生效 |
| 范围 | QQ C2C 受私聊开关控制；频道/频道私信不被误判为 C2C；非消息事件及基础插件保持原行为 |
| 业务副作用 | 禁用人数统计时零抓拍、零推理；禁用公式战时零 API、零数据库写入；禁止群不发送识图提示、不建立 waiter |
| 会话 | 允许群完整完成识图流程；其他群、其他用户图片不能完成该会话；新启动快照变更后的行为正确 |
| 加载 | QQ/OneBot；`ENABLED_PLUGINS=None`、空集合、部分集合；群开关不能加载全局关闭插件；基础插件总是加载；配置错误或选中插件加载失败时非零退出 |
| 快照 | 启动后改文件不即时生效；重新启动后生效；快照不能被 handler 修改 |
| 回归 | 现有人数统计成功/忙碌/失败/关闭测试、公式战数据库及渲染测试、QQ 指令面板测试保持通过 |

分发测试必须调用真实 NoneBot `handle_event()`，使用适配器事件模型、实际注册的响应器和可检查的业务替身；只直接调用 `is_enabled()` 或手动调用 handler 不足以证明闭环。

测试使用临时配置文件、隔离的 dotenv/环境变量及临时业务数据目录，不读取或改写部署配置。子进程启动测试也需纳入覆盖率采集；未采集到的子进程代码不能算作已覆盖。

每个阶段都报告受影响模块的行覆盖率和分支覆盖率，以及上述矩阵中已通过/未通过/未执行的链路。新增 `group_config` 模块要求行覆盖率及分支覆盖率均不低于 95%，剩余未覆盖项逐项说明；群开关允许/禁止、私聊、默认、显式覆盖和传播控制路径必须全部覆盖。

最终在 `nonebot` 目录运行现有完整测试套件并记录覆盖率，不将真实接口未运行误报为通过。示例命令：

```bash
.venv/bin/python -m pytest tests --cov=src --cov-branch --cov-report=term-missing --cov-report=html
```

要求真实分发测试覆盖 QQ 和 OneBot；人工线上验收针对当前实际部署的适配器进行，另一个适配器没有线上环境时明确记录该限制。

### 10.2 真实场景闭环

1. 准备一个允许群、一个禁止群和一个未单独列出的群，填写实际群标识并重启。
2. 允许群触发人数统计：真实群消息 → 群键匹配 → 原有摄像头抓拍 → 原有模型推理 → 实际 QQ 回复。
3. 禁止群触发相同关键词：不回复人数、不触发抓拍；在自动化分发测试中同时证明后续响应器仍收到消息。
4. 在未列出的群核对 `default_enabled=false` 的人数统计和 `default_enabled=true` 的通用插件。
5. C2C 私聊核对人数统计关闭，以及 `enako`、麻将/公式战的私聊规则；原有群专用命令仍执行其原有场景校验。
6. 允许群完成一次 `/识图牌理` 的两消息流程，核对等待、图片识别和最终回复；禁止群无提示和等待会话。
7. 核对公式战群绑定及管理员权限；关闭后不得绑定，已有群绑定数据保留。
8. 修改开关后先验证正在运行的进程仍用原快照，再重启并验证新策略生效。

## 11. 部署与迁移操作

1. 准备发布版本，同时备份现有 `.env`；现有数据库不需要迁移。
2. 从 [examples/group_config.json](examples/group_config.json) 复制文件到宿主机 `/opt/bot-data/plugin_data/group_config.json`，替换群标识并确定开关。
3. 群 ID 使用现有桥实际读取的 `group_id`；QQ 可从已有原始群事件日志核对对应字段，OneBot 使用实际群号。`group_openid` 和群名称均不能替代。
4. `.env` 可显式加入 `GROUP_CONFIG_FILE=/app/plugin_data/group_config.json`；保留现有单摄像头 `PEOPLE_COUNTER_*`、全局 `INPUT_IMG_SIZE` 及业务加载选择。旧的摄像头字段没有被替换，不需要新凭据集合。
5. 升级镜像并重启 `nonebot` 服务。文件必须在新进程启动前存在；默认文件缺失会阻止启动。
6. 检查启动成功及选中插件全部加载，再执行第 10.2 节验收。
7. 后续仅修改 JSON 内容时重启服务；如果修改的是 Docker 服务环境变量，则重新创建服务以载入新环境配置。

若要明确保留当前全部消息行为，可部署 `{}` 文件；若要限制人数统计，采用示例的 `default_enabled=false` 和显式允许群。禁止用自动补文件、异常时放行或读取旧格式实现迁移。

发现问题时回滚镜像及对应配置文件；机器人进程重新启动，原有数据库和摄像头配置无需反向迁移。实施完成后的验收报告必须记录实际文件路径、群策略、测试覆盖率、真实链路结果及未完成项，不能只写“测试通过”。
