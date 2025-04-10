import sqlite3
import os
from .common import *

class Userdata_manager():
    __db_path = userdata_file
    __userdata_format = {
        "uid": "TEXT PRIMARY KEY", 
        "np": "INTEGER"
        }
    def __init__(self) -> None:
        pass

    def __check_userdata(self) -> bool:
        if not self.__ifexist_userdata_table():
            return self.__init_userdata()
        return True
    
    def __ifexist_userdata_table(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'userdata'")
        result = db_cursor.fetchall()[0][0]
        if result > 0:
            return True
        else:
            return False

    def __init_userdata(self) -> bool:
        try:
            db_connection = sqlite3.connect(self.__db_path)
        except:
            return False
        db_cursor = db_connection.cursor()
        db_cursor.execute("CREATE TABLE IF NOT EXISTS userdata(uid TEXT PRIMARY KEY, np INTEGER)")
        db_connection.commit()
        db_cursor.close()
        db_connection.close()
        return True
    
    def __insert_userdata(self, userdata_list: list) -> bool:
        if self.__check_userdata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for userdata in userdata_list:
                db_cursor.execute("INSERT INTO userdata(uid, np) VALUES (?, ?)",
                                (userdata["uid"], userdata["np"]))
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def get_userdata(self, uid_list: list = []) -> list:
        userdata_list = []
        if self.__check_userdata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            if uid_list == []:
                db_cursor.execute("SELECT * FROM userdata")
                result = db_cursor.fetchall()
            else:
                placeholders = ','.join('?' * len(uid_list))
                db_cursor.execute(f"SELECT * FROM userdata WHERE uid IN ({placeholders})", uid_list)
                result = db_cursor.fetchall()
            for row in result:
                userdata = {
                    "uid": row[0],
                    "np": row[1]
                    }
                userdata_list.append(userdata)
            db_cursor.close()
            db_connection.close()
        return userdata_list
    
    def ifexist_userdata(self, uid: str) -> bool:
        if self.__check_userdata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            db_cursor.execute("SELECT COUNT(*) FROM userdata WHERE uid = ?", (uid,))
            result = db_cursor.fetchall()[0][0]
            if result > 0:
                return True
            else:
                return False
        return False

    def update_userdata(self, userdata_list: list) -> bool:
        if self.__check_userdata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            for userdata in userdata_list:
                if self.ifexist_userdata(userdata["uid"]):
                    db_cursor.execute("UPDATE userdata SET np = ? WHERE uid = ?",
                                    (userdata["np"], userdata["uid"]))
                else:
                    self.__insert_userdata([userdata])
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False

    def delete_userdata(self, uid_list: list) -> bool:
        if self.__check_userdata():
            try:
                db_connection = sqlite3.connect(self.__db_path)
            except:
                return False
            db_cursor = db_connection.cursor()
            placeholders = ','.join('?' * len(uid_list))
            db_cursor.execute(f"DELETE FROM userdata WHERE uid IN ({placeholders})", uid_list)
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False
    
    def check_user_np(self, uid: str, np: int) -> bool:
        userdata_list = self.get_userdata(uid_list=[uid])
        if len(userdata_list) == 0 or userdata_list[0]["np"] < np:
            return False
        
        return True
    