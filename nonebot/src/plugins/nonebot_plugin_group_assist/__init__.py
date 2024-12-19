from nonebot import get_plugin_config
from nonebot import on_message
from nonebot import on
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Event, Message, Bot
from nonebot.exception import MatcherException

from .config import Config
from .common import repeat_dict

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-group-assist",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

def is_equal(msg1: Message, msg2: Message):
    if msg1 is None or msg2 is None:
        return False
    if msg1 == msg2:
        return True
    print("mgs1 length: %d", len(msg1))
    if len(msg1) == len(msg1):
        for i in range(len(msg1)):
            if msg1[0].type == msg1[i].type == "image" and msg1[i].data["file"] == msg2[0].data["file"]:
                return True
    
    return False

repeat_message = on(priority=1, block=False)

@repeat_message.handle()
async def repeat_message_handler(event: Event):
    if event.message_type != "group":
        return
    
    group_id = str(event.group_id)
    if event.self_id == event.user_id:
        repeat_dict[group_id] = {
            "message": None,
            "count": 0
        }
        return
    
    print(message)
    message = event.get_message()
    
    if group_id not in repeat_dict.keys():
        repeat_dict[group_id] = {
            "message": message,
            "count": 1
        }
        return
    
    if not is_equal(message, repeat_dict[group_id]["message"]):
        repeat_dict[group_id] = {
            "message": message,
            "count": 1
        }
        return
    
    if is_equal(message, repeat_dict[group_id]["message"]):
        repeat_dict[group_id]["count"] += 1
        
    if repeat_dict[group_id]["count"] < config.repeat_threshold:
        return
    
    repeat_dict[group_id] = {
        "message": None,
        "count": 0
    }
    
    try:
        await repeat_message.finish(event.get_message())
    except MatcherException:
        raise
    except Exception as e:
        pass 