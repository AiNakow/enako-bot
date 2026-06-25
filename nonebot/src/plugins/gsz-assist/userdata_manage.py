import sqlite3
import os
import logging
from contextlib import closing
from .common import gsz_userdata_file

logger = logging.getLogger("gsz_assist")


class Userdata_manager():
    _db_path = gsz_userdata_file
    _DDL = "CREATE TABLE IF NOT EXISTS userdata(uid TEXT PRIMARY KEY, username TEXT)"
    _UPSERT = ("INSERT INTO userdata(uid, username) VALUES(?, ?) "
               "ON CONFLICT(uid) DO UPDATE SET username=excluded.username")

    def __init__(self) -> None:
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        db_connection = sqlite3.connect(self._db_path, timeout=30)
        db_connection.execute("PRAGMA journal_mode=WAL")
        db_connection.execute("PRAGMA busy_timeout=30000")
        return db_connection

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with closing(self._connect()) as db_connection, db_connection:
            db_connection.execute(self._DDL)
        self._initialized = True

    def get_userdata(self, uid_list: list | None = None) -> list:
        self._ensure_initialized()
        uids = uid_list if uid_list else []
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            if not uids:
                db_cursor.execute("SELECT uid, username FROM userdata")
            else:
                placeholders = ",".join("?" * len(uids))
                db_cursor.execute(f"SELECT uid, username FROM userdata WHERE uid IN ({placeholders})", uids)
            result = db_cursor.fetchall()
        return [{"uid": row[0], "username": row[1]} for row in result]

    def ifexist_userdata(self, uid: str) -> bool:
        self._ensure_initialized()
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            db_cursor.execute("SELECT 1 FROM userdata WHERE uid = ? LIMIT 1", (uid,))
            return db_cursor.fetchone() is not None

    def update_userdata(self, userdata_list: list) -> bool:
        self._ensure_initialized()
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            for userdata in userdata_list:
                db_cursor.execute(self._UPSERT, (userdata["uid"], userdata["username"]))
        return True

    def delete_userdata(self, uid_list: list) -> bool:
        self._ensure_initialized()
        if not uid_list:
            return True
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            placeholders = ",".join("?" * len(uid_list))
            db_cursor.execute(f"DELETE FROM userdata WHERE uid IN ({placeholders})", uid_list)
        return True
