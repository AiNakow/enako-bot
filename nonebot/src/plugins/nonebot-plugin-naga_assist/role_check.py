from nonebot.internal.permission import Permission as Permission

from .event_functions import *
from .role_asssgnment import *

async def _NAGA_admin(event: Event) -> bool:
    uid = get_user_id(event)
    return uid in naga_admin

NAGA_ADMIN: Permission = Permission(_NAGA_admin)