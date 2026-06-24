import sqlite3
import os
from .common import *

class Ratedata_manager():
    __db_path = gsz_ratedata_file
    __Ratedata_format = {
        "groupId": "TEXT PRIMARY KEY", 
        "rateId": "INT",
        "rateName": "TEXT"
        }
    def __init__(self) -> None:
        pass

    def __check_ratedata(self) -> bool:
        if not self.__ifexist_ratedata_table():
            return self.__init_ratedata()
        return True
    
    def __ifexist_ratedata_table(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'ratedata'")
        result = db_cursor.fetchall()[0][0]
        db_cursor.close()
        db_connection.close()
        if result > 0:
            return True
        else:
            return False

    def __init_ratedata(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("CREATE TABLE IF NOT EXISTS ratedata(groupId TEXT PRIMARY KEY, rateId INT, rateName TEXT)")
        db_connection.commit()
        db_cursor.close()
        db_connection.close()
        return True
    
    def __insert_ratedata(self, ratedata_list: list) -> bool:
        if self.__check_ratedata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for ratedata in ratedata_list:
                db_cursor.execute("INSERT INTO ratedata(groupId, rateId, rateName) VALUES (?, ?, ?)",
                                (ratedata["groupId"], ratedata["rateId"], ratedata["rateName"]))
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def get_ratedata(self, groupId_list: list = []) -> list:
        ratedata_list = []
        if self.__check_ratedata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            if groupId_list == []:
                db_cursor.execute("SELECT * FROM ratedata")
                result = db_cursor.fetchall()
            else:
                placeholders = ','.join('?' * len(groupId_list))
                db_cursor.execute(f"SELECT * FROM ratedata WHERE groupId IN ({placeholders})", groupId_list)
                result = db_cursor.fetchall()
            for row in result:
                ratedata = {
                    "groupId": row[0],
                    "rateId": row[1],
                    "rateName": row[2]
                    }
                ratedata_list.append(ratedata)
            db_cursor.close()
            db_connection.close()
        return ratedata_list
    
    def ifexist_ratedata(self, groupId: str) -> bool:
        if self.__check_ratedata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            db_cursor.execute("SELECT COUNT(*) FROM ratedata WHERE groupId = ?", (groupId,))
            result = db_cursor.fetchall()[0][0]
            if result > 0:
                return True
            else:
                return False
        return False

    def update_ratedata(self, ratedata_list: list) -> bool:
        if self.__check_ratedata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for ratedata in ratedata_list:
                if self.ifexist_ratedata(ratedata["groupId"]):
                    db_cursor.execute("UPDATE ratedata SET rateId = ?, rateName = ? WHERE groupId = ?",
                                    (ratedata["rateId"], ratedata["rateName"], ratedata["groupId"]))
                else:
                    self.__insert_ratedata([ratedata])
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def delete_ratedata(self, groupId_list: list) -> bool:
        if self.__check_ratedata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            placeholders = ','.join('?' * len(groupId_list))
            db_cursor.execute(f"DELETE FROM ratedata WHERE groupId IN ({placeholders})", groupId_list)
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

