from nonebot.internal.permission import Permission as Permission

from .event_functions import *
from .config import config


async def _NAGA_admin(event: Event) -> bool:
    uid = get_user_id(event)
    return uid in config.naga_assist_admin

NAGA_ADMIN: Permission = Permission(_NAGA_admin)