import sqlite3
import os
import logging
from contextlib import closing
from .common import gsz_ratedata_file

logger = logging.getLogger("gsz_assist")


class Ratedata_manager():
    _db_path = gsz_ratedata_file
    _DDL = ("CREATE TABLE IF NOT EXISTS ratedata"
            "(groupId TEXT PRIMARY KEY, rateId INT, rateName TEXT)")
    _UPSERT = ("INSERT INTO ratedata(groupId, rateId, rateName) VALUES(?, ?, ?) "
               "ON CONFLICT(groupId) DO UPDATE SET rateId=excluded.rateId, rateName=excluded.rateName")

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

    def get_ratedata(self, groupId_list: list | None = None) -> list:
        self._ensure_initialized()
        groupIds = groupId_list if groupId_list else []
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            if not groupIds:
                db_cursor.execute("SELECT groupId, rateId, rateName FROM ratedata")
            else:
                placeholders = ",".join("?" * len(groupIds))
                db_cursor.execute(f"SELECT groupId, rateId, rateName FROM ratedata WHERE groupId IN ({placeholders})", groupIds)
            result = db_cursor.fetchall()
        return [{"groupId": row[0], "rateId": row[1], "rateName": row[2]} for row in result]

    def ifexist_ratedata(self, groupId: str) -> bool:
        self._ensure_initialized()
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            db_cursor.execute("SELECT 1 FROM ratedata WHERE groupId = ? LIMIT 1", (groupId,))
            return db_cursor.fetchone() is not None

    def update_ratedata(self, ratedata_list: list) -> bool:
        self._ensure_initialized()
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            for ratedata in ratedata_list:
                db_cursor.execute(self._UPSERT, (ratedata["groupId"], ratedata["rateId"], ratedata["rateName"]))
        return True

    def delete_ratedata(self, groupId_list: list) -> bool:
        self._ensure_initialized()
        if not groupId_list:
            return True
        with closing(self._connect()) as db_connection, db_connection:
            db_cursor = db_connection.cursor()
            placeholders = ",".join("?" * len(groupId_list))
            db_cursor.execute(f"DELETE FROM ratedata WHERE groupId IN ({placeholders})", groupId_list)
        return True
