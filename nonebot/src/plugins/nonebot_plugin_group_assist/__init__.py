from nonebot import get_plugin_config
from nonebot import on_message
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Event
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

repeat_message = on_message(priority=1, block=False)

@repeat_message.handle()
async def repeat_message_handler(event: Event):
    print(repeat_dict)
    if event.self_id == event.user_id:
        return
    
    if event.message_type != "group":
        return
    
    group_id = str(event.group_id)
    if group_id not in repeat_dict.keys():
        repeat_dict[group_id] = {
            "message": event.raw_message,
            "count": 1
        }
        return
    
    if event.raw_message != repeat_dict[group_id]["message"]:
        repeat_dict[group_id] = {
            "message": event.raw_message,
            "count": 1
        }
        return
    
    if event.raw_message in repeat_dict[group_id]:
        repeat_dict[group_id]["count"] += 1
        
    if repeat_dict[group_id]["count"] != config.repeat_threshold:
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