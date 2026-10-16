"""JOIN table objects ported from ``JoinTable.cs``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .column import CastColumn, Column
from .sql import SQLExecute, OpType, SQLOperator
from .table import ITable, Table
from .where import Where

from exceptions import PRISError

class JoinType(Enum):
    INNER_JOIN = 0
    LEFT_JOIN = 1
    RIGHT_JOIN = 2
    OUTER_JOIN = 3
    InnerJoin = INNER_JOIN
    LeftJoin = LEFT_JOIN
    RightJoin = RIGHT_JOIN
    OuterJoin = OUTER_JOIN


@dataclass(frozen=True)
class _JoinCondition:
    left: Column
    right: Column
    operator: OpType
    outer_operator: OpType
    ignore_if_null: Column | None = None
    ignore_if_null2: Column | None = None


class JoinOn:
    def __init__(self, left: Column | None = None, right: Column | None = None,
                 operator: OpType = OpType.EQUAL,
                 ignore_if_null: Column | None = None,
                 ignore_if_null2: Column | None = None):
        self.conditions: list[_JoinCondition] = []
        if left is not None and right is not None:
            self.add(left, right, operator, OpType.AND, ignore_if_null, ignore_if_null2)

    def add(self, left: Column, right: Column, operator: OpType = OpType.EQUAL,
            add_operator: OpType = OpType.AND, ignore_if_null: Column | None = None,
            ignore_if_null2: Column | None = None) -> None:
        self.conditions.append(_JoinCondition(
            left, right, operator, add_operator, ignore_if_null, ignore_if_null2
        ))

    Add = add

    @staticmethod
    def _belongs_to(column: Column, table: ITable) -> bool:
        current = column.table
        while True:
            if current is table:
                return True
            if current.outer is current:
                return False
            current = current.outer

    def to_sql(self, left_table: ITable, right_table: ITable, collate: str = "") -> str:
        parts: list[str] = []
        for index, condition in enumerate(self.conditions):
            if not self._belongs_to(condition.left, left_table):
                raise ValueError(f"欄位 {condition.left.alias} 不屬於表格 {left_table.alias}")
            if not self._belongs_to(condition.right, right_table):
                raise ValueError(f"欄位 {condition.right.alias} 不屬於表格 {right_table.alias}")
            expression = (
                f"([{left_table.alias}].[{condition.left.alias}] "
                f"{SQLOperator(condition.operator)} "
                f"[{right_table.alias}].[{condition.right.alias}]{collate}"
            )
            if condition.ignore_if_null:
                expression += (
                    f" OR [{condition.ignore_if_null.table.alias}]"
                    f".[{condition.ignore_if_null.alias}] IS NULL"
                )
            if condition.ignore_if_null2:
                expression += (
                    f" OR [{condition.ignore_if_null2.table.alias}]"
                    f".[{condition.ignore_if_null2.alias}] IS NULL"
                )
            expression += ")"
            if index:
                expression = f"{SQLOperator(condition.outer_operator)} {expression}"
            parts.append(expression)
        return " ".join(parts)

    def __str__(self) -> str:
        raise PRISError("Use JoinOn.to_sql(left_table, right_table, collate)")


class JoinTable(ITable):
    def __init__(self, left: ITable, right: ITable, join_type: JoinType,
                 on: JoinOn, collate: str | None = None,
                 ignore_auto_collate: bool = False):
        super().__init__()
        self.outer = self           # ITable 不再提供預設值,與 C# 一致由子類別自行設定
        self.left, self.right = left, right
        self.left.outer = self
        self.right.outer = self
        self.join_type = join_type
        self.on = on
        self.collate = collate or ""
        self.columns: list[Column] = []
        if not ignore_auto_collate:
            self._set_collate()
        self._alias = Table.register_alias(f"{left.alias}_JOIN_{right.alias}")

    @property
    def alias(self) -> str:
        return self._alias

    @alias.setter
    def alias(self, value: str) -> None:
        self._alias = value

    def get_column(self, name: str) -> Column | None:
        for column in [*self.columns, *self.left.get_columns(), *self.right.get_columns()]:
            if column.name == name:
                return column
        return None

    GetColumn = get_column

    def retrieve_column(self, major: Column, minor: Column, name: str) -> Column:
        column = Column.coalesce(self, major, minor, name)
        self.columns.append(column)
        return column

    RetrieveColumn = retrieve_column

    def get_cast_column(self, cast_columns: Iterable[Column], name: str) -> CastColumn:
        column = CastColumn(cast_columns, self, name)
        self.columns.append(column)
        return column

    GetCastColumn = get_cast_column

    def copy_table(self, table: ITable | None = None, alias: str = "") -> "JoinTable":
        source = table or self
        if not isinstance(source, JoinTable):
            raise PRISError("限制傳入類別為 JoinTable")
        copied = JoinTable(source.left, source.right, source.join_type, source.on,
                           source.collate, ignore_auto_collate=True)
        copied.columns = source.columns.copy()
        copied._alias = Table.register_alias(alias or f"{source.alias}_COPY")
        copied.outer = copied if source.outer is source else source.outer
        return copied

    CopyTable = copy_table

    def get_tables(self) -> list[Table]:
        return [*self.left.get_tables(), *self.right.get_tables()]

    GetTables = get_tables

    def find_first_table(self, full_table_name: str) -> Table | None:
        return next((table for table in self.get_tables()
                     if table.full_name == Table(full_table_name).full_name), None)

    FindFirstTable = find_first_table

    def get_columns(self) -> list[Column]:
        return [*self.left.get_columns(), *self.right.get_columns(), *self.columns]

    def inner_cols_to_string(self) -> str:
        columns = [
            *(column.to_outer_string(self.left.alias) for column in self.left.get_columns()),
            *(column.to_outer_string(self.right.alias) for column in self.right.get_columns()),
            *(column.to_inner_string() for column in self.columns),
        ]
        return ",".join(columns)

    def outer_cols_to_string(self, replacements: dict[Column, str] | None = None) -> str:
        replacements = replacements or {}
        columns = self.get_columns()
        return ",".join(
            f"N'{replacements[column].replace(chr(39), chr(39) * 2)}'"
            if column in replacements else column.to_outer_string(self.alias)
            for column in columns
        )

    def get_join_keyword(self) -> str:
        return {
            JoinType.INNER_JOIN: "INNER JOIN",
            JoinType.LEFT_JOIN: "LEFT JOIN",
            JoinType.RIGHT_JOIN: "RIGHT JOIN",
            JoinType.OUTER_JOIN: "FULL OUTER JOIN",
        }[self.join_type]

    def _collate_sql(self) -> str:
        return f" COLLATE {self.collate}" if self.collate else ""

    def get_inner_select_clause(self) -> str:
        return (
            f"SELECT {self.inner_cols_to_string()} FROM ({self.left.get_inner_select_clause()}) [{self.left.alias}] "
            f"{self.get_join_keyword()} ({self.right.get_inner_select_clause()}) [{self.right.alias}] "
            f"ON {self.on.to_sql(self.left, self.right, self._collate_sql())}"
        )

    def create_temp_table(self, create_def: str | None = None) -> None:
        if not self.tmp_table_name:
            raise PRISError("tmp_table_name must be set before creating a temp table")
        command = (f"CREATE TABLE {self.tmp_table_name} ({create_def})" if create_def else
                   f"SELECT TOP 0 {self.outer_cols_to_string()} INTO {self.tmp_table_name} "
                   f"FROM ({self.get_inner_select_clause()}) [{self.alias}]")
        SQLExecute.do_no_query(command)


    def insert_temp_table_range(self, col: Column, val:int, less_val:int, wheres:list[Where] = None, distinct:bool = True):
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] > {val} AND [{col.alias}] < {less_val}{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_list(self, col: Column, val:list[str], wheres:list[Where] = None, distinct:bool = True):

        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)

        cmd_base = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}]"
        )

        for index in range(0, len(val), 300):
            in_vals = ",".join(f"N'{self._escape_sql_string(str(item))}'" for item in val[index:index + 300])
            str_cmd = f"{cmd_base} IN ({in_vals}){where_str}"    
            SQLExecute.do_no_query(str_cmd)
        return 


    def insert_temp_table_op(self, col: Column, val:int, op:str = "=", wheres:list[Where] = None, distinct:bool = True):
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] {op} {val}{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_eq_str(self, col: Column, val:str, wheres:list[Where] = None, distinct:bool = True):
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] = N'{self._escape_sql_string(str(val))}'{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_partial(self, col: Column, val:str, partial: bool, keep_orig: bool, shown_val:str=None,wheres:list[Where]=None, distinct:bool=True):
        select_cols = self.outer_cols_to_string({col : shown_val if shown_val is not None else str(val)}) if keep_orig else self.outer_cols_to_string()
        distinct_str = self.get_distinct_str(distinct)
        wildcard_char = "%" if partial else ""
        where_str = self.where_clause_to_string(wheres)
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] LIKE N'{self._escape_sql_string(str(val))}{wildcard_char}'{where_str}"
        )
    
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table(self,col: Column,wheres:list[Where]=None, distinct:bool=True):
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] IS NOT NULL{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    # [說明] 原本這段「自動偵測兩邊 DB 定序不同就補 COLLATE」其實從未生效:
    #   - Table 沒有 `.db` 屬性(是 `.db_name`)→ AttributeError 被 except 吞掉
    #   - SQLExecute.query 回傳 DataFrame,`[0]["COLLATION_NAME"]` 也會 KeyError
    # 為了讓「結果與目前版本一致」,修正後預設仍關閉(AUTO_COLLATE=False)。
    # 若要啟用(與原 C# 行為一致),設 JoinTable.AUTO_COLLATE = True 並做結果比對。
    AUTO_COLLATE = False
    _DB_COLLATION_CACHE: dict[str, str] = {}

    @classmethod
    def _get_db_collation(cls, db_name: str) -> str | None:
        if db_name not in cls._DB_COLLATION_CACHE:
            rows = SQLExecute.query_2d_raw(
                "SELECT collation_name FROM sys.databases WHERE name = ?", params=(db_name,)
            )
            cls._DB_COLLATION_CACHE[db_name] = rows[0][0] if rows else None
        return cls._DB_COLLATION_CACHE[db_name]

    def _set_collate(self) -> None:
        if not self.AUTO_COLLATE:
            return
        if isinstance(self.left, JoinTable) or isinstance(self.right, JoinTable) or self.collate:
            return
        try:
            left = self._get_db_collation(self.left.db_name)
            right = self._get_db_collation(self.right.db_name)
            if left and right and left != right:
                self.collate = str(left)
        except Exception:
            self.collate = self.collate or ""


class YJoinTable(JoinTable):
    def __init__(self, table:JoinTable, need_year_func_wrap:bool=True):
        super().__init__(table.left, table.right, table.join_type, table.on, table.collate)
        self.need_year_func_wrap = need_year_func_wrap
        self.columns = table.columns
        for col in self.columns:
            col.table = self
        self.alias = table.alias

    def insert_temp_table(self, 
                          col: Column,
                          label:str,
                          val:int, 
                          less_val:int=None,
                          wheres:list[Where] = None) -> None:
        
        if not self.tmp_table_name:
            raise PRISError("tmp_table_name must be set before inserting")
        
        where_str = self.where_clause_to_string(wheres)
        columns = self.outer_cols_to_string()
        col_expr = self.year_func_wrap(f"[{self.alias}].[{col.alias}]")

        prefix = (
            f"INSERT INTO {self.tmp_table_name} SELECT {columns}, '{self._escape_sql_string(str(label))}' "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE {col_expr}"
        )
        if less_val is None:
            statement = f"{prefix} = {int(val)}{where_str}"
        else:
            # [Bug fix] 原本是 list,cursor.execute(list) 會 TypeError;'{label}'FROM 中間也少了空白
            statement = f"{prefix} > {int(val)} AND {col_expr} < {int(less_val)}{where_str}"
        
        SQLExecute.do_no_query(statement)

    def add_label_col(self, col_name):
        # [Bug fix] 原本簽名是 (conn, col_name) 且呼叫不存在的 sql_execute_do_non_query,
        #           Subject 只傳一個參數 → TypeError。與 YTable.add_label_col 對齊。
        cmd = f"ALTER TABLE {self.tmp_table_name} ADD [{col_name}] varchar(32)"
        SQLExecute.do_no_query(cmd)

    def year_func_wrap(self, param):
        if self.need_year_func_wrap:
            return f"YEAR({param})"
        return f"{param}"