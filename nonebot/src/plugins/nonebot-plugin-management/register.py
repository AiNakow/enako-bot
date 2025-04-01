from nonebot.plugin import Plugin
from .plugindata_manage import PluginDataManager
from .config import config

class PluginRegister:
    plugin_data_manager = PluginDataManager()

    def __init__(self):
        self.plugin_list: list[Plugin] = []
        self.disable_dict: dict = {}
        self.hidden_plugins: list[str] = config.hidden_plugins
        """
        {
            "plugin_name": {
                "group_id": list[str],
                "global_disable": bool
            }
        }
        """

        self.load_plugin_setting()

    def register(self, plugin: Plugin):
        if plugin.name in self.hidden_plugins:
            return
        self.plugin_list.append(plugin)

    def load_plugin_setting(self) -> bool:
        plugin_disable_data_list = self.plugin_data_manager.get_plugin_data()
        for plugin_disable_data in plugin_disable_data_list:
            self.disable_dict[plugin_disable_data["plugin_name"]] = {
                "group_id": plugin_disable_data["group_id"].split(","),
                "global_disable": plugin_disable_data["global_disable"]
            }
        
    def get_plugin_help_list(self, group_id: str) -> list[str]:
        help_list = []
        for plugin in self.plugin_list:
            if not self.if_plugin_disable(plugin.metadata.name, group_id):
                help_list.append(plugin.metadata.usage)
        return help_list

    def get_plugin_list(self, group_id: str) -> dict[str, list[str]]:
        """
        return {
            "enable": [],
            "disable": []
        }
        """
        result = {
            "enable": [],
            "disable": []
        }

        for plugin in self.plugin_list:
            if self.if_plugin_disable(plugin.metadata.name, group_id):
                result["disable"].append(plugin.metadata.name)
            else:
                result["enable"].append(plugin.metadata.name)
        return result

    def enable_plugin(self, plugin_name: str, group_id: str):
        plugin_disable_data = self.disable_dict.get(plugin_name, {})
        if plugin_disable_data == {}:
            return
        if group_id in plugin_disable_data["group_id"]:
            plugin_disable_data["group_id"].remove(group_id)

        group_id_str = ",".join(plugin_disable_data["group_id"])
        self.plugin_data_manager.update_plugin_data([{
            "plugin_name": plugin_name,
            "group_id": group_id_str,
            "global_disable": plugin_disable_data["global_disable"]
        }])

    def disable_plugin(self, plugin_name: str, group_id: str):
        plugin_disable_data = self.disable_dict.get(plugin_name, {})
        if plugin_disable_data == {}:
            plugin_disable_data = {
                "group_id": [],
                "global_disable": False
            }
        plugin_disable_data["group_id"].append(group_id)

        self.disable_dict[plugin_name] = plugin_disable_data
        group_id_str = ",".join(plugin_disable_data["group_id"])
        self.plugin_data_manager.update_plugin_data([{
            "plugin_name": plugin_name,
            "group_id": group_id_str,
            "global_disable": plugin_disable_data["global_disable"]
        }])
            

    def if_plugin_disable(self, plugin_name: str, group_id: str) -> bool:
        plugin_disable_data = self.disable_dict.get(plugin_name, {})
        print(plugin_disable_data)
        print(group_id)
        if plugin_disable_data == {}:
            return False
        if not plugin_disable_data["global_disable"] and group_id not in plugin_disable_data["group_id"]:
            return False
        return True
    
    def if_plugin_exist(self, plugin_name: str) -> bool:
        for plugin in self.plugin_list:
            if plugin.metadata.name == plugin_name:
                return True
        return False
        
plugin_register = PluginRegister()