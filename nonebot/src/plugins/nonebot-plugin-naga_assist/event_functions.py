from nonebot.adapters import Event

def get_user_id(event: Event) -> int:
    return event.get_user_id()