import sqlite3
from .common import *

class PluginDataManager:
    __db_path = plugin_data_file
    __plugin_data_format = {
        "plugin_name": "TEXT PRIMARY KEY",
        "plugin_status": "TEXT"
    }

    def __init__(self):
        pass
    
    def __check_plugin_data(self):
        if not os.path.exists(self.__db_path):
            self.__init_plugin_data()
        return True
    
    def __init_plugin_data(self):
        pass
    
    def __insert_plugin_data(self, plugin_data: dict):
        pass
    
    
    