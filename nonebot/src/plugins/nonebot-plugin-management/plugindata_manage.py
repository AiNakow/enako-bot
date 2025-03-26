import sqlite3
from .common import *


class PluginDataManager:
    __db_path = plugin_data_file
    __plugin_data_format = {
        "plugin_name": "TEXT PRIMARY KEY",
        "group_id": "TEXT",
        "global_disable": "BOOLEAN"
    }

    def __init__(self):
        pass

    def __check_plugin_data(self) -> bool:
        if not self.__ifexist_plugin_data_table():
            return self.__init_plugin_data()
        return True
    
    def __ifexist_plugin_data_table(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'plugin_data'")
        result = db_cursor.fetchall()[0][0]
        db_cursor.close()
        db_connection.close()
        if result > 0:
            return True
        else:
            return False

    def __init_plugin_data(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("CREATE TABLE IF NOT EXISTS plugin_data(plugin_name TEXT PRIMARY KEY, group_id TEXT, global_disable BOOLEAN)")
        db_connection.commit()
        db_cursor.close()
        db_connection.close()
        return True
    
    def __insert_plugin_data(self, plugin_data_list: list) -> bool:
        if self.__check_plugin_data():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for plugin_data in plugin_data_list:
                db_cursor.execute("INSERT INTO plugin_data(plugin_name, group_id, global_disable) VALUES (?, ?, ?)",
                                (plugin_data["plugin_name"], plugin_data["group_id"], plugin_data["global_disable"]))
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def get_plugin_data(self, plugin_name_list: list = []) -> list:
        plugin_data_list = []
        if self.__check_plugin_data():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            if plugin_name_list == []:
                db_cursor.execute("SELECT * FROM plugin_data")
                result = db_cursor.fetchall()
            else:
                placeholders = ','.join('?' * len(plugin_name_list))
                db_cursor.execute(f"SELECT * FROM plugin_data WHERE plugin_name IN ({placeholders})", plugin_name_list)
                result = db_cursor.fetchall()
            for row in result:
                plugin_data = {
                    "plugin_name": row[0],
                    "group_id": row[1],
                    "global_disable": row[2]
                    }
                plugin_data_list.append(plugin_data)
            db_cursor.close()
            db_connection.close()
        return plugin_data_list
    
    def ifexist_plugin_data(self, plugin_name: str) -> bool:
        if self.__check_plugin_data():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            db_cursor.execute("SELECT COUNT(*) FROM plugin_data WHERE plugin_name = ?", (plugin_name,))
            result = db_cursor.fetchall()[0][0]
            if result > 0:
                return True
            else:
                return False
        return False

    def update_plugin_data(self, plugin_data_list: list) -> bool:
        if self.__check_plugin_data():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for plugin_data in plugin_data_list:
                if self.ifexist_plugin_data(plugin_data["plugin_name"]):
                    db_cursor.execute("UPDATE plugin_data SET group_id = ?, global_disable = ? WHERE plugin_name = ?",
                                    (plugin_data["group_id"], plugin_data["global_disable"], plugin_data["plugin_name"]))
                else:
                    self.__insert_plugin_data([plugin_data])
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def delete_plugin_data(self, plugin_name_list: list) -> bool:
        if self.__check_plugin_data():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            placeholders = ','.join('?' * len(plugin_name_list))
            db_cursor.execute(f"DELETE FROM plugin_data WHERE plugin_name IN ({placeholders})", plugin_name_list)
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False