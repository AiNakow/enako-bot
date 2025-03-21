class PluginRegister:
    def __init__(self):
        self.plugin_help_list = []
        self.enable_plugin_list = []
        self.disable_plugin_list = []

    def register(self, plugin_help_command: str):
        self.plugin_help_list.append(plugin_help_command)
        
    def get_plugin_help_list(self):
        return self.plugin_help_list

    def get_plugin_list(self):
        pass

    def enable_plugin(self, plugin_name: str):
        pass

    def disable_plugin(self, plugin_name: str):
        pass
        
plugin_register = PluginRegister()