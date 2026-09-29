"""可复制的 NoneBot 人数统计目录；导入本包不会自动注册插件。"""
import asyncio

from nonebot import get_driver, on_command, on_keyword

from .config import Config, create_service
from .person_counter import CounterError

service = create_service()
busy = asyncio.Lock()
matcher = on_keyword({"音游几","中二几","舞萌几"},
                    priority=10,
                    block=True)


@matcher.handle()
async def handle_people_count():
    if busy.locked():
        await matcher.finish("检测人数中，请不要频繁查询。")
    async with busy:
        try:
            count = await service.count_async()
            counts = await service.machine_occupancy_async()
        except CounterError:
            await matcher.finish("人数检测失败，请检查摄像头连接、配置或模型。")
        message = f"音游房当前有 {count} 人。\n" + "当前已上机人数：\n" + "\n".join(
            f"{name}：{count} 人" for name, count in counts.items()) + "\n（当前结果基于监控图像识别）"
        await matcher.finish(message)


@get_driver().on_shutdown
async def shutdown():
    await service.aclose()