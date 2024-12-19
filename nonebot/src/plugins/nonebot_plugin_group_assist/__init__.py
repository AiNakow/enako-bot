from nonebot import get_plugin_config
from nonebot import on_message
from nonebot import on
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Event, Message, Bot
from nonebot.exception import MatcherException

from .config import Config
from .common import repeat_dict, repeat_dict_lock

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-group-assist",
    description="群聊小助手，包含复读机等功能",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

def is_equal(msg1: Message, msg2: Message):
    if msg1 is None or msg2 is None:
        return False
    flag = True
    if len(msg1) == len(msg2):
        for i in range(len(msg1)):
            if msg1[i] != msg2[i]:
                if msg1[i].type == msg2[i].type == "image" and msg1[i].data["file_unique"] == msg2[i].data["file_unique"]:
                    continue
                
                if msg1[i].type == msg2[i].type == "forward":
                    # print("msg1: ", msg1[i].data["content"])
                    # print("msg2: ", msg2[i].data["content"])
                    # print(msg1[i].data["content"] == msg2[i].data["content"])
                    if msg1[i].data["content"] == msg2[i].data["content"]:
                        continue
                flag = False
                break
    else:
        flag = False
        
    return flag

on_message_sent = on("message_sent", priority=1, block=False)
repeat_message = on_message(priority=1, block=False)

@on_message_sent.handle()
async def on_message_sent_handler(event:Event):    
    if event.message_type != "group":
        return
    group_id = str(event.group_id)
    with repeat_dict_lock:
        if event.self_id == event.user_id:
            repeat_dict[group_id] = {
                "message": None,
                "count": 0,
                "time": 0
            }

@repeat_message.handle()
async def repeat_message_handler(event: Event):
    if event.message_type != "group":
        return
    
    group_id = str(event.group_id)
    # print(event.raw_message)
    message = event.get_message()
    with repeat_dict_lock:
        if group_id not in repeat_dict.keys():
            repeat_dict[group_id] = {
                "message": message,
                "count": 1,
                "time": event.time
            }
            return
        
        # 冷却时间
        if event.time - repeat_dict[group_id]["time"] < config.repeat_cd:
            return
        
        if not is_equal(message, repeat_dict[group_id]["message"]):
            repeat_dict[group_id] = {
                "message": message,
                "count": 1,
                "time": event.time
            }
            return
        
        if is_equal(message, repeat_dict[group_id]["message"]):
            repeat_dict[group_id]["count"] += 1
            
        if repeat_dict[group_id]["count"] < config.repeat_threshold:
            return
        
        repeat_dict[group_id] = {
            "message": None,
            "count": 0,
            "time": 0
        }
        
        try:
            await repeat_message.finish(event.get_message())
        except MatcherException:
            raise
        except Exception as e:
            pass 