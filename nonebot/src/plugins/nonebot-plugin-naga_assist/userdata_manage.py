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
                db_cursor.execute("INSERT INTO userdata(uid, np) \
                                    VALUES ('{0}', {1})".format(
                                    userdata["uid"],
                                    userdata["np"]
                                ))
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
                db_cursor.execute("SELECT * FROM userdata WHERE uid in ({0})".format(", ".join("'{0}'".format(uid) for uid in uid_list)))
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
            db_cursor.execute("SELECT COUNT(*) FROM userdata WHERE uid = '{0}'".format(uid))
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
                    db_cursor.execute("UPDATE userdata \
                                    SET np = {1}\
                                    WHERE uid = '{0}'".format(
                                        userdata["uid"],
                                        userdata["np"]
                                    ))
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
            db_cursor.execute("DELETE FROM userdata WHERE uid IN ({0})".format(", ".join("'{0}'".format(uid) for uid in uid_list)))
            db_connection.commit()
            db_cursor.close()
            db_connection.close()
            return True
        return False
    
    def check_user_np(self, uid: str, np: int) -> bool:
        userdata = self.get_userdata(uid_list=[uid])[0]
        if userdata["np"] < np:
            return False
        
        return True


# test
if __name__ == "__main__":
    userdata_list = [
        {"uid":"1234567890", "np": 500},
        {"uid":"0987654321", "np": 2500}
    ]
    userdata_manager = Userdata_manager()
    print(userdata_manager.update_userdata(userdata_list=userdata_list))
    print(userdata_manager.get_userdata())
    print(userdata_manager.delete_userdata(["1234567890"]))
    print(userdata_manager.get_userdata(["0987654321"]))
    print(userdata_manager.ifexist_userdata("0987654321"))
    print(userdata_manager.ifexist_userdata("1234567890"))


    