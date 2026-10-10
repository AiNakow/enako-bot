"""Apply group/private policy before a business matcher runs."""
from nonebot.adapters import Event
from nonebot.exception import IgnoredException
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor

from src.infrastructure_plugins._adapter import bridge

from .config import validate_group_key
from .service import has_policy, initialize_group_config, is_enabled, resolve_business_plugin

__all__ = ["initialize_group_config"]


@run_preprocessor
async def apply_group_policy(matcher: Matcher, event: Event) -> None:
    plugin_name = resolve_business_plugin(matcher)
    if plugin_name is None or event.get_type() != "message" or not has_policy(plugin_name):
        return
    group_key = None
    if bridge.is_group_event(event):
        group_id = bridge.get_group_id(event)
        try:
            if group_id is None:
                raise ValueError("missing group ID")
            group_key = f"{bridge.name}:{group_id}"
            validate_group_key(group_key)
        except ValueError as error:
            logger.warning(f"Group config skipped plugin {plugin_name}: {error}")
            raise IgnoredException("invalid conversation group ID") from None
        scope = "group"
    elif bridge.is_private_event(event):
        scope = "private"
    else:
        return
    if not is_enabled(plugin_name, scope=scope, group_key=group_key):
        raise IgnoredException("plugin disabled for this conversation")
