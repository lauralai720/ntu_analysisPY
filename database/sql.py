"""
Connects to a SQL database using mssql-python

[優化版] 主要變更:
- get_connection() 不再每次呼叫都送 SELECT 1(原本每個 SQL 都多一次 round-trip,且 cursor 不關閉)
- do_no_query 可選擇不 commit,搭配 transaction() 一次 commit
- 欄位型別查詢改用「既有連線 + 三段式名稱 + 參數化 + 快取」,不再每次開新連線
- 暫存表登錄/清除機制 (register_temp_table / drop_temp_tables)
- 密碼含 ; 或 } 時的連線字串跳脫
"""
import threading
import time
from contextlib import contextmanager

import mssql_python
import pandas as pd
from enum import Enum

from exceptions import PRISError

class OpType(Enum):
    EQUAL = 0
    NOT_EQUAL = 1
    LIKE = 2
    IN = 3
    NOT_IN = 4
    LESS_THAN = 5
    GREATER_THAN = 6
    LESS_THAN_EQUAL = 7
    GREATER_THAN_EQUAL = 8
    IS = 9
    IS_NOT = 10
    AND = 11
    OR = 12
    BITWISE_AND = 13

    # C#-style member aliases for a low-friction migration.
    Equal = EQUAL
    NotEqual = NOT_EQUAL
    Like = LIKE
    In = IN
    NotIn = NOT_IN
    LessThan = LESS_THAN
    GreaterThan = GREATER_THAN
    LessThanEqual = LESS_THAN_EQUAL
    GreaterThanEqual = GREATER_THAN_EQUAL
    Is = IS
    IsNot = IS_NOT
    And = AND
    Or = OR
    BitwiseAnd = BITWISE_AND


_OPERATORS = (
    "=", "!=", "LIKE", "IN", "NOT IN", "<", ">", "<=", ">=",
    "IS", "IS NOT", "AND", "OR", "&",
)


class SQLOperator:
    def __init__(self, operator_type: OpType):
        self.type = operator_type

    def __str__(self) -> str:
        return _OPERATORS[self.type.value]


_DB_CONFIG = {
    "server": "",
    "username": "",
    "password": "",
    # 預設維持原行為(加密 + 信任憑證);正式環境若有正確憑證建議改為 False
    "trust_server_certificate": True,
}

_connection: "mssql_python.Connection | None" = None
_last_ok: float = 0.0           # 最近一次確認連線可用的時間 (monotonic)
_PING_INTERVAL_SEC = 60.0       # 超過這個閒置時間才 ping 一次
_conn_lock = threading.RLock()


def _escape_conn_value(value: str) -> str:
    """ODBC 連線字串的值若含 ; { } 需用 {} 包起來,} 要寫成 }}"""
    if any(ch in value for ch in ";{}"):
        return "{" + value.replace("}", "}}") + "}"
    return value


def _build_conn_str(database: str | None = None) -> str:
    parts = [
        f"Server={_DB_CONFIG['server']}",
        f"UID={_escape_conn_value(_DB_CONFIG['username'])}",
        f"PWD={_escape_conn_value(_DB_CONFIG['password'])}",
    ]
    if database:
        parts.append(f"DATABASE={database}")
    parts.append("Encrypt=yes")
    parts.append("TrustServerCertificate=" + ("yes" if _DB_CONFIG["trust_server_certificate"] else "no"))
    return ";".join(parts) + ";"


class DB():
    @staticmethod
    def set_connection(host: str, username: str, pwd: str) -> bool:
        global _connection
        with _conn_lock:
            _DB_CONFIG["server"] = host
            _DB_CONFIG["username"] = username
            _DB_CONFIG["password"] = pwd
            _connection = None          # 換了連線資訊就丟掉舊連線
        return DB.get_connection() is not None

    @staticmethod
    def _ping(conn) -> bool:
        try:
            with conn.cursor() as cur:       # [優化] 用 with 確保 cursor 被關閉
                cur.execute("SELECT 1")
                cur.fetchall()
            return True
        except Exception:
            return False

    @staticmethod
    def get_connection() -> "mssql_python.Connection":
        """
        取得共用連線。
        [優化] 原本每次呼叫都 `conn.cursor().execute("SELECT 1")` 檢查連線,
        800 筆 INSERT 就多 800 次 round-trip 與 800 個沒關的 cursor。
        現在只有「閒置超過 _PING_INTERVAL_SEC」才 ping 一次。

        注意: #暫存表是 session 等級,連線一旦重連,暫存表就消失。
        所以重連時會 log 警告,避免後續出現難以理解的 'Invalid object name #TEMPTBLx'。
        """
        global _connection, _last_ok
        with _conn_lock:
            now = time.monotonic()
            if _connection is not None and (now - _last_ok) > _PING_INTERVAL_SEC:
                if not DB._ping(_connection):
                    print("[警告] DB 連線已中斷,重新連線;原 session 的 #暫存表已失效")
                    _TEMP_TABLES.clear()
                    _connection = None
            if _connection is None:
                _connection = mssql_python.connect(_build_conn_str())
            _last_ok = now
            return _connection

    @staticmethod
    def close() -> None:
        global _connection
        with _conn_lock:
            if _connection is not None:
                try:
                    _connection.close()
                finally:
                    _connection = None
                    _TEMP_TABLES.clear()


# ---------------------------------------------------------------------------
# 暫存表登錄:#暫存表在連線存活期間會一直佔用 tempdb,長時間執行 / 多次呼叫 run_report 會累積
# ---------------------------------------------------------------------------
_TEMP_TABLES: list[str] = []


class SQLExecute():
    @staticmethod
    def drop_temp_sql(name: str) -> str:
        # 不用 DROP TABLE IF EXISTS (需 SQL Server 2016+),改用舊版也支援的寫法
        return f"IF OBJECT_ID('tempdb..{name}') IS NOT NULL DROP TABLE {name}"

    @staticmethod
    def register_temp_table(name: str) -> None:
        if name not in _TEMP_TABLES:
            _TEMP_TABLES.append(name)

    @staticmethod
    def forget_temp_table(name: str) -> None:
        if name in _TEMP_TABLES:
            _TEMP_TABLES.remove(name)

    @staticmethod
    def drop_temp_tables() -> None:
        """清掉本程式建立的所有 #暫存表 (run_report 結束時呼叫)"""
        if not _TEMP_TABLES:
            return
        conn = DB.get_connection()
        with conn.cursor() as cursor:
            for name in list(_TEMP_TABLES):
                try:
                    cursor.execute(SQLExecute.drop_temp_sql(name))
                except Exception as e:      # 清理失敗不應該蓋掉原本的錯誤
                    print(f"[警告] 刪除暫存表 {name} 失敗: {e}")
            conn.commit()
        _TEMP_TABLES.clear()

    @staticmethod
    def commit() -> None:
        DB.get_connection().commit()

    @staticmethod
    @contextmanager
    def transaction():
        """
        with SQLExecute.transaction(): 內的多筆 do_no_query(commit=False) 最後一次 commit,
        出錯整批 rollback。
        """
        conn = DB.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def query(sql_cmd: str, params=None) -> pd.DataFrame:
        _conn = DB.get_connection()
        if _conn is None:
            raise PRISError("尚未設定DB連線，請先呼叫 get_connection()。")

        # print(sql_cmd)
        # print()
        with _conn.cursor() as cursor:
            if params:
                cursor.execute(sql_cmd, params)
            else:
                cursor.execute(sql_cmd)
            df = cursor.arrow().to_pandas()
        return df

    @staticmethod
    def query_2d_raw(sql_cmd: str, conn=None, params=None) -> list[list[str]]:
        _conn = conn if conn is not None else DB.get_connection()
        if _conn is None:
            raise PRISError("尚未設定DB連線，請先呼叫 get_connection()。")
        with _conn.cursor() as cursor:
            if params:
                cursor.execute(sql_cmd, params)
            else:
                cursor.execute(sql_cmd)
            rows = cursor.fetchall()
        return rows

    @staticmethod
    def do_no_query(sql_cmd: str, params=None, commit: bool = True):
        """
        [優化] 新增 commit 參數。批次建立暫存表資料時請用 commit=False,
        最後再一次 commit(或包在 transaction() 內),可省掉大量 log flush。
        """
        _conn = DB.get_connection()
        if _conn is None:
            raise PRISError("尚未設定DB連線，請先呼叫 get_connection()。")

        # print(sql_cmd)
        # print()
        with _conn.cursor() as cursor:
            if params:
                cursor.execute(sql_cmd, params)
            else:
                cursor.execute(sql_cmd)
        if commit:
            _conn.commit()

    @staticmethod
    def do_exist_query(sql_cmd: str) -> bool:
        rows = SQLExecute.query_2d_raw(sql_cmd)
        return bool(rows and rows[0][0])

    @staticmethod
    def do_count_query(sql_cmd: str) -> int:
        rows = SQLExecute.query_2d_raw(sql_cmd)
        return int(rows[0][0])


# ---------------------------------------------------------------------------
# 欄位型別查詢 (給 Bind 判斷要不要加 COLLATE)
# [優化] 原本 Bind.__str__ 每次都會 mssql_python.connect() 開「新連線」且從不關閉,
#        一份報表會呼叫幾十~幾百次。改為: 既有連線 + 三段式名稱 + 參數化 + 快取。
# ---------------------------------------------------------------------------
_COLUMN_TYPE_CACHE: dict[tuple[str, str, str], str | None] = {}


def get_column_data_type(db_name: str, table_name: str, column_name: str) -> str | None:
    key = (db_name.lower(), table_name.lower(), column_name.lower())
    if key in _COLUMN_TYPE_CACHE:
        return _COLUMN_TYPE_CACHE[key]

    safe_db = db_name.replace("]", "]]")
    rows = SQLExecute.query_2d_raw(
        f"SELECT DATA_TYPE FROM [{safe_db}].INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
        params=(table_name, column_name),
    )
    result = rows[0][0] if rows and len(rows[0]) > 0 else None
    _COLUMN_TYPE_CACHE[key] = result
    return result
