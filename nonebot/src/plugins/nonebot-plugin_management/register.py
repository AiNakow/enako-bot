class PluginRegister:
    def __init__(self):
        self.plugin_help_list = []
        
    def register(self, plugin_help_command):
        self.plugin_help_list.append(plugin_help_command)
        
    def get_plugin_help_list(self):
        return self.plugin_help_list()
        
plugin_register = PluginRegister()