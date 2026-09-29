# 复制到 NoneBot 的人数统计服务

这是一个普通 Python 目录，不是安装包。包含抓拍、YOLO26n ONNX 模型、玻璃区域过滤、重复框去重、三台音游机器上机人数统计、NoneBot 配置适配和可选示例插件。不含真实凭据、监控照片、运行结果或虚拟环境。

## 1. 复制目录并安装依赖

将整个 `nonebot_people_counter/` 放在机器人项目根目录，与 `bot.py` 同级。Python 3.10+。

```text
机器人项目/
├── bot.py
├── .env.prod
└── nonebot_people_counter/
    ├── config.py
    ├── plugin.py
    ├── nonebot.env.example
    ├── requirements.txt
    └── person_counter/
        ├── detector.py
        ├── service.py
        ├── capture.py
        ├── postprocess.py
        ├── regions.py
        ├── glass_region.json
        ├── machine_areas.py
        ├── machine_areas.json
        └── models/yolo26n.onnx
```

在**机器人使用的 Python 环境**中执行，Windows/Linux 命令相同：

```sh
python -m pip install -r nonebot_people_counter/requirements.txt
```

已包含约 9.3 MB 的 ONNX 模型，使用 ONNX Runtime 在 CPU 上推理。服务器不需要 PyTorch、Ultralytics、OpenCV 或模型导出工具；仍需 requirements.txt 中的 onnxruntime、NumPy、Pillow、requests，及机器人已有的 NoneBot。不会在线下载模型。

## 2. 填入 NoneBot 环境配置

把 `nonebot.env.example` 的配置合并到机器人**实际加载的环境文件**。例如 `.env` 中设置 `ENVIRONMENT=prod` 时使用 `.env.prod`；开发环境可能是 `.env.dev`。不要覆盖现有文件。最少填写：

```dotenv
PEOPLE_COUNTER_APP_KEY=原EZVIZ_APP_KEY的值
PEOPLE_COUNTER_APP_SECRET=原EZVIZ_APP_SECRET的值
PEOPLE_COUNTER_DEVICE_SERIAL=原EZVIZ_DEVICE_SERIAL的值
PEOPLE_COUNTER_CHANNEL_NO=原EZVIZ_CHANNEL_NO的值
```

如果使用授权 Token，填 `PEOPLE_COUNTER_ACCESS_TOKEN`；它优先于 AppKey/AppSecret，失效时需更新。这里没有自动带走旧密钥，需要你从原 `.env` 复制相应值。

完整模板还包括置信度、推理尺寸、CPU 推理线程数、抓拍间隔、超时和去重阈值。模型、玻璃区域和游玩区域路径以 `nonebot_people_counter/` 为基准，改变启动目录不影响路径。两种区域标定只适用于当前固定机位；更换机位后需要重新标定。

**配置读取方式**：NoneBot 初始化时读取 dotenv/系统环境变量，插件通过 `get_plugin_config(Config)` 获取类型化字段，再转成服务的 `Settings`。这里不会调用 `load_dotenv()`、不会重新读取服务自己的 `.env`，也不依赖 `os.getenv()` 能读到 dotenv 的内容。NoneBot 从 dotenv 加载配置不等于把这些值写进 `os.environ`。系统环境变量也可使用相同 `PEOPLE_COUNTER_*` 名称，按 NoneBot 配置优先级生效。

```python
from nonebot import get_plugin_config
from nonebot_people_counter.config import Config

config = get_plugin_config(Config)  # 必须在 nonebot.init() 之后
channel_no = config.people_counter_channel_no
# 密钥使用 SecretStr 包装；需要时调用 get_secret_value()，不要打印密钥。
```

字段采用独立的 `PEOPLE_COUNTER_` 前缀，避免与其他插件配置冲突。修改环境文件后需要重启机器人。官方依据：[NoneBot 配置文档](https://nonebot.dev/docs/appendices/config)。

## 3A. 在已有插件内调用（推荐）

```python
from nonebot import get_driver
from nonebot_people_counter.config import create_service
from nonebot_people_counter.person_counter import Camera, CounterError

# 在插件模块级创建一次；模型在首次请求时延迟加载，并复用。
service = create_service()

async def your_existing_handler():
    try:
        count = await service.count_async()  # int，使用默认摄像头
    except CounterError:
        # 在你的 handler 中回复失败，不要返回 0。
        return "人数检测失败，请稍后重试。"
    return f"当前室内画面检测到 {count} 人。"

# 新增接口：返回固定顺序的 dict[str, int]
occupancy = await service.machine_occupancy_async()
# {"中二": 1, "舞萌左": 2, "舞萌右": 1}

# 同时需要总人数和上机人数时，共用一次抓拍和一次模型推理：
count, occupancy = await service.count_with_occupancy_async()

# 如果要指定另一路摄像头：
# count = await service.count_async(Camera("NVR序列号", 2))
# 与默认摄像头不同的序列号/通道不应用默认玻璃标定，但仍做重复框去重。

@get_driver().on_shutdown
async def close_people_counter():
    await service.aclose()
```

`your_existing_handler()` 只是展示返回结果，你需要在现有 matcher 中调用并发送消息。不必同时加载示例插件。使用多个插件时共享同一个 service，避免重复加载模型与绕过抓拍间隔限制。`count_async()` 不阻塞事件循环，但同一实例的推理串行执行；建议像示例插件一样对忙碌请求直接回复，不让消息无限排队。

## 3B. 直接加载自带示例插件

在现有 `bot.py` 的 `nonebot.init()` 之后、`nonebot.run()` 之前添加：

```python
nonebot.load_plugin("nonebot_people_counter.plugin")
```

保留你现有的驱动、适配器注册及其他插件。若通过 `pyproject.toml` 管理插件，则将 `nonebot_people_counter.plugin` **追加**到现有 `[tool.nonebot]` 的 `plugins` 列表，不要重复用两种方式加载。

示例命令为 `店内人数` 和 `上机人数`，受机器人现有 `COMMAND_START` 控制，通常发送 `/店内人数` 或 `/上机人数`。后者返回中二、舞萌左、舞萌右各自人数。示例使用 `SUPERUSER` 权限，需要在现有 `SUPERUSERS` 列表中配置你的账号。两个命令共用模型和忙碌锁，关闭机器人时释放资源。

## 调用约定与限制

- `await service.count_async()`：返回当前图片的人数整数。未检测到人为 0，失败抛 `CounterError`。
- `await service.machine_occupancy_async()`：返回 `{"中二": int, "舞萌左": int, "舞萌右": int}`，上限依次为 1、2、2。
- `await service.count_with_occupancy_async()`：返回 `(总人数, 各机器上机人数)`，仅抓拍、解码、推理一次，两项统计共享过滤、去重后的检测结果；仅支持默认摄像头，失败抛 `CounterError`。`handle_people_count()` 使用此接口。
- `service.count_with_occupancy()`：联合统计的同步版本。
- `service.count()`：同步版本，不要直接在异步 handler 中执行。
- `service.count_image(path)`：用本地同机位图片调试，避免消耗抓拍额度；这也是同步调用。
- `service.machine_occupancy()` / `service.machine_occupancy_image(path)`：新增接口的同步和离线版本。
- `await service.aclose()`：关闭时等待在途任务并释放会话。
- 自动 Token 在服务实例内缓存；同摄像头抓拍最小间隔 5 秒；图片仅在内存中处理。
- 原图检测后过滤玻璃区，再按 IoU 0.50 去重；这减少重复计数，不能保证解决遮挡漏检或所有误检。
- 每个人框只分配给重合比例最高且达到 0.60 的一个游玩区域，不会跨机器重复计数。区域人数达到机器上限后封顶。
- 游玩区域只标定了默认摄像头；向 `machine_occupancy()` 传入其他摄像头会抛出 `CounterError`，避免返回错误数据。
- 外层协程取消不会强行终止已开始的工作线程，不要通过极短的异步超时反复重试。

首次验证可先在你已有插件中调用一次，确认摄像头可访问，再接命令。移交目录为独立 ONNX 实现，之后修改原项目不会自动更新这里。

## ONNX 实现与配置迁移

- `detector.py`：RGB 输入、等比例双线性缩放、补边、ONNX 推理、坐标还原及检测头候选框 NMS。
- `postprocess.py`：无效框过滤、玻璃区域排除和人物去重。保留先排除玻璃、再执行业务去重的顺序。
- `machine_areas.py`：把保留的人物框分配给重合比例最高的机器区域，并按 1、2、2 人封顶。
- `service.py`：抓拍及同步/异步调用；`config.py`：读取 NoneBot 配置。

模型使用 FP32、opset 17，动态输入 `[batch, 3, height, width]`，输出 `[batch, 84, anchors]`；84 个通道为中心坐标/宽高和 80 类分数。输入长边默认 640，短边补到 32 的倍数。只统计 COCO 的 person 类（ID 0）。原始候选框先按 IoU 0.7 做模型级 NMS（最多 300 框），随后按玻璃标定和 `PEOPLE_COUNTER_NMS_IOU=0.50` 做业务过滤。两次贪心 NMS 不能直接合并为一次，否则保留的候选框可能变化。

更新已有部署时，整体替换旧目录，并调整机器人环境配置：

```dotenv
PEOPLE_COUNTER_MODEL_PATH=person_counter/models/yolo26n.onnx
PEOPLE_COUNTER_THREADS=2
```

删除旧的 `PEOPLE_COUNTER_DEVICE` 和 `PEOPLE_COUNTER_MAX_DETECTIONS` 配置。插件只有 ONNX CPU 执行路径，不保留 `.pt` 加载或 Ultralytics 回退。`PEOPLE_COUNTER_IMAGE_SIZE` 必须为 32 的倍数；`PEOPLE_COUNTER_THREADS` 控制 ONNX 算子内部线程数。

模型已转换完成，服务器无需再次导出。此次在开发环境使用 Ultralytics 8.4.164 从原 `yolo26n.pt` 导出，参数如下（仅供记录）：

```python
YOLO("yolo26n.pt").export(
    format="onnx", imgsz=640, dynamic=True, simplify=False,
    opset=17, nms=None, device="cpu", batch=1,
)
```

此版本导出器中的 `nms=None` 选择原始 one-to-many 检测头；`nms=False` 会改为 one-to-one 端到端检测头，其输出结构和检测结果不同。不要用其他输出结构的 ONNX 文件直接替换本模型。

## 交付验证

2026-09-29：在不安装 PyTorch、Ultralytics、OpenCV 的独立 Python 3.13 环境验证 ONNX 推理；5 张已有监控样本的最终人数依次为 **3、7、8、6、6**，与原服务一致。此结果验证迁移前后的一致性，不代表人工标注的绝对准确率。

音游区域使用 2796×1580 的原始机位标定。5 张样本的上机统计依次为 `0/2/0`、`1/2/1`、`1/2/2`、`1/0/1`、`1/2/2`（中二/舞萌左/舞萌右）。该结果是区域占用判定；仅凭单帧人物框无法判断玩家是否正在操作屏幕。

复制到临时机器人目录后，测试环境文件读取、系统环境变量覆盖、模型/标定路径解析、两个插件命令、忙碌拒绝、错误回复及关闭清理。测试使用虚拟凭据与模拟抓拍结果，不连接聊天平台。本次未重新请求真实摄像头。
