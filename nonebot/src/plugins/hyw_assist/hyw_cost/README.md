# 计费核心使用说明

本目录是独立的 Python 计费包，已在 CPython 3.12.10 验收，运行时仅依赖标准库。调用方提供同一用户的访问记录、一份完整配置及必要的试算终点，核心从空状态重放并返回计算结果。

当前版本按日间、具体夜间实例分别封顶，跨日夜的费用可能叠加；没有整次访问或滚动 24 小时统一封顶配置。早鸟有独立上限，并与所在基础时段、当日日间共享预算。

## 1. 导入与调用

在本仓库运行时，将 `src` 加入模块搜索路径：

```powershell
$env:PYTHONPATH = 'src'
```

公共入口是 `calculate_bill(visits, config, *, as_of=None) -> BillResult`。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `visits` | 内置 `list[Visit]` 或 `tuple[Visit, ...]` | 非空，同一用户截至目标本次访问的完整历史，或符合规则的完整后缀 |
| `config` | `BillingConfig` | 下节的全部字段均须显式传入，核心没有默认配置 |
| `as_of` | `datetime` 或 `None` | 只能按关键字传入；本次未出场时必须提供，本次已出场时省略或传 `None` |

核心复制并按绝对入场时间排序，入场最晚的访问为“本次”。调用不会改写原容器或模型，也不会读取机器当前时间、数据库或付款状态。

同一次调用的一份固定 `config` 应用于全部传入访问及其相关前史，不支持按访问分别传历史价格或配置版本。更换配置表示按新配置重新计算该历史，调用方须同时重新判断所需历史范围。

## 2. 完整配置及字段解释

### BillingConfig

| 字段 | 确切类型 | 示例 | 含义与约束 |
| --- | --- | --- | --- |
| `day_start` | `datetime.time` | `time(12, 0)` | 每日日间开始时间；严格早于 `night_start` |
| `night_start` | `datetime.time` | `time(22, 0)` | 每日夜间开始时间，也是当日日间结束时间 |
| `hourly_rate_fen` | `int` | `2000` | 统一小时单价，单位为分；示例为 20 元/小时，也是首小时价格 |
| `day_cap_fen` | `int` | `7800` | 每个日间实例的封顶额度，单位为分；同时计入当日早鸟实际应收 |
| `night_cap_fen` | `int` | `7800` | 每个夜间实例的封顶额度，单位为分；夜间跨午夜仍使用同一份预算 |
| `first_hour_free_seconds` | `int` | `900` | 首小时免费阈值，单位为秒，范围 `0..3599`；累计进度恰好等于阈值仍免费，超过后触发首笔小时价 |
| `step_seconds` | `int` | `900` | 首小时结束后的普通计费步长，单位为秒；每满一个完整步长产生费用，不满不收 |
| `early_bird` | `EarlyBirdConfig` 或 `None` | 见下表 | 早鸟配置；关闭早鸟必须显式传入 `None` |

日间为日期 D 的 `[day_start, night_start)`，夜间为 D 的 `night_start` 到 D+1 的 `day_start`，两者无缝覆盖全天。区间左闭右开，例如恰在 22:00 真实入场属于夜间。

`hourly_rate_fen`、`day_cap_fen`、`night_cap_fen`、`step_seconds` 的合法整数范围都是 `1..2**63-1`。不接受 `bool`、`float`、`Decimal`、字符串或子类；例如 20 元须传 `2000`，不能传 `20.0` 或 `"2000"`。

各封顶之间、封顶与单价之间没有大小关系约束，封顶可以低于首小时价格。

首小时固定为 3600 秒，计费时区固定为北京时间 UTC+08:00，均不是配置项。`step_seconds` 可以不整除 3600，也可以大于 3600；每步理论费用为 `hourly_rate_fen * step_seconds / 3600`，核心按费用归属时段累计精算后采用 HALF_UP 舍入到分，再应用封顶。

### EarlyBirdConfig

| 字段 | 确切类型 | 示例 | 含义与约束 |
| --- | --- | --- | --- |
| `start` | `datetime.time` | `time(8, 0)` | 当日早鸟开始时间，严格早于 `end` |
| `end` | `datetime.time` | `time(12, 0)` | 当日早鸟结束时间；起止必须在同一自然日，不能隐式跨午夜 |
| `cap_fen` | `int` | `3000` | 每日早鸟封顶额度，单位为分，严格整数范围 `1..2**63-1` |

所有配置时间必须无 `tzinfo` 且 `fold=0`，支持微秒；不接受时间字符串或 `24:00`。早鸟允许与日间、夜间重叠，也可以跨基础日夜边界。位于早鸟时，费用优先归属早鸟，同时受早鸟、当日日间及当前基础时段的去重预算约束；同一笔实际费用只收一次。不预占整份早鸟额度，仅共享实际应收。

配置模型及 `Visit` 都只能用关键字构造，所有字段必填，没有默认值；模型不可变，构造时只承载字段，实际校验由 `calculate_bill()` 完成。缺少字段、额外字段或错误的位置参数由 Python 抛出 `TypeError`。不支持直接传配置字典，也没有 `timezone`、`day_end` 等额外配置字段。

## 3. 访问记录、时间与历史要求

| Visit 字段 | 类型 | 说明 |
| --- | --- | --- |
| `entered_at` | `datetime.datetime` | 真实入场时间，必须带合法固定偏移时区 |
| `exited_at` | `datetime.datetime` 或 `None` | 真实出场时间，必须严格晚于入场；未出场也须显式填写 `None` |

时间要求：

- `entered_at`、非空 `exited_at` 和使用中的 `as_of` 必须是确切的 `datetime`，其 `tzinfo` 必须是标准库 `datetime.timezone`；不接受无时区时间、`ZoneInfo`、自定义时区或 `datetime` 子类。
- 固定偏移须为整分钟，范围为 -23:59 到 +23:59，`fold=0`。可以传 UTC 等合法固定偏移，核心统一按北京时间确定窗口及统计日期。
- 转为北京时间后的日期必须在 `0002-01-01` 到 `9998-12-31` 内；时间精度支持微秒。
- 同一用户的访问不得重复或重叠，相邻两条“前次出场等于后次入场”合法，并仍是两次真实访问。
- 只能有一条未出场访问，且它必须是入场最晚的一条。未出场时 `as_of >= entered_at`；相等允许零时长试算，零时长的已出场记录则非法。

调用方需要保存权威访问历史。已经付款的访问仍可能影响后续进度和封顶，不能因付款、归档、跨午夜或只显示当天统计而删除输入历史。核心每次从所传记录重放，不能自动识别漏传历史。

只有早鸟关闭，或 `early_bird.end <= night_start` 时，才可按以下规则选取完整后缀：从目标终点的北京时间统计日前一天 `night_start` 开始逐日向前寻找最近安全边界 B；候选日期须在支持域内。安全要求没有真实访问严格跨过 B，即不存在 `entered_at < B < exited_at`，未出场访问只要入场早于 B 就算跨过，不能将 `as_of` 当作真实出场。找到后保留全部 `entered_at >= B`、截至目标本次的原始完整记录。没有可用候选、所有候选均被跨过，或配置不符合资格时，传真实首次入场以来的完整历史。

边界检查及后缀读取必须使用同一份权威历史一致视图；更换目标、终点、配置或修改历史后须重新选取。首次集成建议直接提供完整历史。

## 4. 完整使用样例：历史早鸟 + 本次日间试算

以下配置是可修改的示例，完整包含所有必填字段。代码可以放在能导入 `hyw_cost` 的脚本中运行。

```python
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from hyw_cost import BillingConfig, EarlyBirdConfig, Visit, calculate_bill

BEIJING = timezone(timedelta(hours=8))

config = BillingConfig(
    day_start=time(12, 0),
    night_start=time(22, 0),
    hourly_rate_fen=2000,                 # 20 元/小时
    day_cap_fen=7800,                     # 日间封顶 78 元
    night_cap_fen=7800,                   # 每个夜间封顶 78 元
    first_hour_free_seconds=15 * 60,      # 累计不超过 15 分钟免费
    step_seconds=15 * 60,                 # 首小时后每满 15 分钟收费
    early_bird=EarlyBirdConfig(
        start=time(8, 0),
        end=time(12, 0),
        cap_fen=3000,                     # 早鸟封顶 30 元
    ),
)

visits = [
    Visit(
        entered_at=datetime(2026, 10, 31, 8, 0, tzinfo=BEIJING),
        exited_at=datetime(2026, 10, 31, 10, 0, tzinfo=BEIJING),
    ),
    Visit(
        entered_at=datetime(2026, 10, 31, 14, 0, tzinfo=BEIJING),
        exited_at=None,
    ),
]
as_of = datetime(2026, 10, 31, 14, 16, tzinfo=BEIJING)
result = calculate_bill(visits, config, as_of=as_of)

assert result.stat_date.isoformat() == "2026-10-31"
assert result.current_payable_fen == 2000
assert result.current_presence_seconds == Decimal("960")
assert result.daily_presence_seconds.early_bird == Decimal("7200")
assert result.daily_presence_seconds.day == Decimal("960")
assert result.daily_presence_seconds.night == Decimal("7200")

# 展示时可以转为小时、分钟，计算与 JSON 保留精确秒数。
hours, minutes = divmod(int(result.current_presence_seconds) // 60, 60)
yuan, fen = divmod(result.current_payable_fen, 100)
print(f"本次在场：{hours}小时{minutes}分")  # 0小时16分，不足一分钟舍去
print(f"本次新增应收：{yuan}.{fen:02d} 元")  # 20.00 元
print(result.to_json())
```

前次早鸟应收 30 元，本次日间新增 20 元；`current_payable_fen` 返回 `2000`，不是两次费用合计 `5000`。早鸟实际收费会占用当日日间额度，但不会提前给未来日间授予首小时覆盖。

输出 JSON：

```json
{"stat_date":"2026-10-31","daily_presence_seconds":{"early_bird":7200,"day":960,"night":7200},"current_presence_seconds":960,"current_payable_fen":2000}
```

## 5. 其他调用样例

本节代码分别沿用第 4 节的 `config`、`visits`、`as_of`、`result`、`BEIJING` 及导入。

### 真实出场结算及后续返场

```python
from dataclasses import replace

# 模型不可变，生成包含真实出场时间的新记录，随后交由应用层保存。
closed_visits = [*visits[:-1], replace(visits[-1], exited_at=as_of)]
settled = calculate_bill(closed_visits, config)  # 已出场，不传 as_of
assert settled == result
assert settled.to_json() == result.to_json()

# 追加真实返场，重新提供此前完整历史。
returned_visits = [
    *closed_visits,
    Visit(
        entered_at=datetime(2026, 10, 31, 15, 0, tzinfo=BEIJING),
        exited_at=datetime(2026, 10, 31, 15, 59, tzinfo=BEIJING),
    ),
]
returned = calculate_bill(returned_visits, config)
assert returned.current_payable_fen == 500
assert returned.current_presence_seconds == Decimal("3540")
```

试算不会产生真实出场，也不会在核心内部保存结算状态。同一历史、配置和终点重复计算会得到相同结果。插件层负责保存出入场事实、收费结果以及支付流水。

### 跨午夜访问

```python
night_visits = [
    Visit(
        entered_at=datetime(2026, 10, 31, 23, 30, tzinfo=BEIJING),
        exited_at=datetime(2026, 11, 1, 0, 45, tzinfo=BEIJING),
    ),
]
night_result = calculate_bill(night_visits, config)
assert night_result.stat_date.isoformat() == "2026-11-01"
assert night_result.current_presence_seconds == Decimal("4500")  # 本次完整 75 分钟
assert night_result.daily_presence_seconds.night == Decimal("2700")  # 当天 45 分钟
assert night_result.current_payable_fen == 2500
```

### 关闭早鸟

```python
from dataclasses import replace

config_without_early = replace(config, early_bird=None)
ordinary_result = calculate_bill([
    Visit(
        entered_at=datetime(2026, 10, 31, 8, 0, tzinfo=BEIJING),
        exited_at=datetime(2026, 10, 31, 14, 30, tzinfo=BEIJING),
    ),
], config_without_early)
assert ordinary_result.daily_presence_seconds.early_bird == Decimal("0")
assert ordinary_result.current_payable_fen == 12800  # 夜间 78 元 + 日间 50 元
```

`early_bird=False`、空字典或省略字段都不能用来关闭早鸟。

## 6. 返回结果与异常

| 返回字段 | 类型 | 含义 |
| --- | --- | --- |
| `stat_date` | `datetime.date` | 本次真实出场或 `as_of` 的北京时间日期 |
| `daily_presence_seconds.early_bird` | `Decimal` | 全部输入记录在统计日内与早鸟窗口重叠的实际秒数，关闭早鸟时为零 |
| `daily_presence_seconds.day` | `Decimal` | 全部输入记录在统计日内与日间窗口重叠的实际秒数 |
| `daily_presence_seconds.night` | `Decimal` | 全部输入记录在统计日内与夜间窗口重叠的实际秒数，可包括前夜和当晚，但两份预算仍独立 |
| `current_presence_seconds` | `Decimal` | 本次真实入场到本次终点的完整秒数，跨日不截短 |
| `current_payable_fen` | `int` | 本次访问新增的实际应收，单位为分；不含前次欠费，也不扣付款流水 |

当天总在场时长等于 `day + night`，早鸟与基础时段可能重叠，不能再把 `early_bird` 加入总时长。所有时长都精确到整数微秒，整秒也返回 `Decimal`。

`result.to_json()` 返回紧凑 JSON 字符串；日期为 ISO 字符串，金额为整数 number，时长为十进制 number，最多六位小数，不经过 `float`。需要精确反解时：

```python
import json

decoded = json.loads(result.to_json(), parse_float=Decimal)
assert decoded["current_payable_fen"] == result.current_payable_fen
assert Decimal(decoded["current_presence_seconds"]) == result.current_presence_seconds
```

可捕获的业务输入异常为 `BillingConfigError`、`BillingInputError`，均继承 `BillingError(ValueError)`，具有只读的 `code`、`field`。例如未出场却漏传试算终点：

```python
from hyw_cost import BillingError

try:
    calculate_bill(visits, config)  # 第 4 节的最新访问尚未出场
except BillingError as error:
    assert error.code == "AS_OF_REQUIRED"
    assert error.field == "as_of"
    print(f"计费输入错误：{error.code}，字段：{error.field}")
```

字段类型错误通常为 `INVALID_TYPE`，配置超界为 `OUT_OF_RANGE`；已出场却传非空 `as_of` 为 `AS_OF_NOT_ALLOWED`。模型参数绑定错误是 `TypeError`；内部不变量损坏是 `RuntimeError`，不应作为可忽略的输入问题处理。

## 7. 放入 NoneBot 插件

将整个 `hyw_cost` 目录作为插件内部子包，例如：

```text
your_plugin/
  __init__.py
  hyw_cost/
    __init__.py
    models.py
    errors.py
    validation.py
    calculation.py
    serialization.py
    README.md
```

在插件的 `__init__.py` 中使用相对导入：

```python
from .hyw_cost import BillingConfig, EarlyBirdConfig, Visit, calculate_bill
```

其余用法与上文一致。插件负责命令处理、用户隔离、读取一致的权威历史、选择目标终点、构造模型和展示结果；核心保持普通同步函数，不依赖 NoneBot，也不进行数据库或网络调用。数据库字段或外部配置需要在插件层显式转换为本说明要求的 Python 类型。
