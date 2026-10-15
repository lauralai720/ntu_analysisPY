from abc import ABC, abstractmethod
import secrets

from exceptions import PRISError
from .column import Column
from .where import Where
from .sql import SQLExecute


class ITable(ABC):
    def __init__(self):
        self.outer: ITable = self
        self.tmp_table_name: str | None = None

    @property
    @abstractmethod
    def alias(self) -> str: 
        ...
    @abstractmethod
    def create_temp_table(self, create_def: str | None = None) -> None: ...

    @abstractmethod
    def insert_temp_table(self, col: Column, wheres:list[Where] = None, distinct:bool = True) -> None: ...

    @property
    def outmost(self):
        current = self
        while current.outer is not current:
            current = current.outer
        return current
    
    @staticmethod
    def where_clause_to_string(wheres: list[Where], use_and:bool = True) -> str:
        
        connet_str = "AND"
        if use_and == False:
            connet_str = "OR"
        clauses = [str(w) for w in wheres or ()]
        str_where = ""
        if clauses:
            str_where = f" {connet_str} " + f" {connet_str} ".join(clauses)
        
        return str_where

    @abstractmethod
    def get_columns(self) -> list["Column"]: ...

    @abstractmethod
    def get_tables(self) -> list["Table"]: ...

    @abstractmethod
    def get_column(self, column: str) -> "Column | None": ...

    @abstractmethod
    def copy_table(self, table: "ITable", alias: str = "") -> "ITable": ...

    @abstractmethod
    def get_inner_select_clause(self) -> str: ...

    def get_distinct_str(self, distinct:bool)->str:
        return "DISTINCT " if distinct else ""
    
    @staticmethod
    def _escape_sql_string(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _chunks(seq, size: int):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    @staticmethod
    def build_values_rows(pairs: list[tuple[str, str]]) -> str:
        """[(key, pattern), ...] -> (N'k',N'p'),(N'k',N'p')...  (單引號已跳脫)"""
        esc = ITable._escape_sql_string
        return ",".join(f"(N'{esc(str(k))}',N'{esc(str(p))}')" for k, p in pairs)

class Table(ITable):
    _existing_aliases: set[str] = set()
    def __init__(self, full_name: str, db_name: str | None = None, table = None, alias: str = ""):
        super().__init__()

        # COPY Table的狀態
        if table and isinstance(table, Table):
            self.table_name = table.table_name
            self.db_name = table.db_name
            self.columns = table.columns
            # [Bug fix] 原本 `self.outer == table` 在此時永遠是 False(self.outer 剛被設成 self),
            # 導致「複製最外層 Table」後,複本的 outmost 會指回原 Table。
            # 正確語意: 若來源本身是最外層 → 複本也是最外層;否則沿用來源的 outer。
            self.outer = self if table.outer is table else table.outer
            if not alias:
                alias = f"{self.table_name.lower()}_COPY"
            self._alias = self.register_alias(alias)
            return

        if db_name is None:
            parts = full_name.split(".")
            if len(parts) != 3:
                raise ValueError("資料表名稱格式限定為 XXX.dbo.YYY")
            self.table_name = parts[2].strip("[]")
            self.db_name = parts[0].strip("[]")
        else:
            self.table_name = full_name
            self.db_name = db_name

        self.outer = self
        self.columns :set[Column] = set()
        if not alias:
            alias = self.table_name.lower()

        self._alias = self.register_alias(alias)

    @property
    def full_name(self) -> str:
        return f"[{self.db_name}].dbo.[{self.table_name}]"

    def set_full_name(self, full_name: str) -> None:
        parts = full_name.split(".")
        if len(parts) != 3:
            raise PRISError("資料表名稱格式限定為 XXX.dbo.YYY")
        self.db_name, self.table_name = parts[0].strip("[]"), parts[2].strip("[]")

    SetFullName = set_full_name

    @property
    def alias(self) -> str:
        return self._alias
    
    def _check_column(self, column: Column) -> None:
        if column.table is not self:
            raise PRISError("Column 物件不適用於此 Table 物件上")

    # 轉list[table]
    def get_tables(self) -> list:
        return [self]

    def get_column(self, col_name:str)-> Column | None:
        return next((item for item in self.columns if item.name == col_name), None)

    GetColumn = get_column

    def get_columns(self) -> list[Column]:
        return self.columns.copy()

    @staticmethod
    def copy_table(table:ITable, alias: str = "") -> "Table":
        if not isinstance(table, ITable):
            raise PRISError("table 參數必須是 ITable 的實例")
        new_table = Table(table=table, alias=alias)    
        return new_table

    def outer_cols_to_string(self, col_replace_const : dict[str, Column] = None)->str:
        if not col_replace_const:
            return ",".join([f"{col.alias}" for col in self.columns])

        return ",".join(
            f"N'{col_replace_const[c]}'" if c in col_replace_const else f"[{c.alias}]"
            for c in self.columns
        )
    
    def inner_cols_to_string(self, col_replace_const : dict[str, Column] = None)->str:
        if not col_replace_const:
            return ",".join([f"{col.to_inner_string()}" for col in self.columns])

        return ",".join(
            f"N'{col_replace_const[c]}'" if c in col_replace_const else f"[{c.to_inner_string()}]"
            for c in self.columns
        )
    

    def get_inner_select_clause(self) -> str:
        return f"(SELECT {self.inner_cols_to_string()} FROM {self.full_name} [{self.alias}])"

    def retrieve_column(self, name: str, concat: list[str] | None = None,
                        func: str | None = None) -> Column:
        existing = self.get_column(name)
        if existing is not None:
            return existing

        if func is not None:
            concat = None
            column = Column(self, name, func=func, concat=concat)
        else:
            column = Column(self, name, concat=concat)

        self.columns.add(column)
        return column
    
    RetrieveColumn = retrieve_column

    def create_temp_table(self,  create_def: str | None = None) -> None:
        if not self.tmp_table_name:
            raise PRISError("尚未設定暫存表名稱，請先設定tmp_table_name。")
        
        if create_def is not None:
            command = f"CREATE TABLE {self.tmp_table_name} ({create_def})"
        else:
            command = (
                f"SELECT TOP 0 {self.outer_cols_to_string()} INTO {self.tmp_table_name} "
                f"FROM ({self.get_inner_select_clause()}) [{self.alias}]"
            )
        SQLExecute.do_no_query(command)

    def before_insert_check(self, col: Column):
        if not self.tmp_table_name:
            raise PRISError("尚未設定暫存表名稱，請先設定tmp_table_name。")
        self._check_column(col)
    
    def insert_temp_table_range(self, col: Column, val:int, less_val:int, wheres:list[Where] = None, distinct:bool = True):
        self.before_insert_check(col)
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] > {val} AND [{col.alias}] < {less_val}{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_list(self, col: Column, val:list[str], wheres:list[Where] = None, distinct:bool = True):
        self.before_insert_check(col)
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


    _ALLOWED_OPS = frozenset({"=", "!=", "<>", "<", ">", "<=", ">="})

    def insert_temp_table_op(self, col: Column, val:int, op:str = "=", wheres:list[Where] = None, distinct:bool = True):
        self.before_insert_check(col)
        if op not in self._ALLOWED_OPS:          # [安全] op / val 是直接拼進 SQL 的,先驗證
            raise PRISError(f"不支援的比較運算子: {op}")
        val = int(val)

        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] {op} {val}{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_eq_str(self, col: Column, val:str, wheres:list[Where] = None, distinct:bool = True):
        self.before_insert_check(col)

        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] = N'{self._escape_sql_string(str(val))}'{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    def insert_temp_table_partial(self, col: Column, val:str, partial: bool, keep_orig: bool, shown_val:str=None,wheres:list[Where]=None, distinct:bool=True):
        self.before_insert_check(col)

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
        self.before_insert_check(col)
        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)
        
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}{select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE [{col.alias}] IS NOT NULL{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    @classmethod
    def register_alias(cls, alias:str) -> str:
        alias = alias or secrets.token_hex(4).upper()

        candidate = alias
        index = 1
        while candidate in cls._existing_aliases:
            candidate = f"{alias}_{index}"
            index += 1

        cls._existing_aliases.add(candidate)
        return candidate

class YTable(Table):
    def __init__(self, table:Table, need_year_func_wrap=True):
        super().__init__(table.table_name, table.db_name, table.alias)
        self.need_year_func_wrap = need_year_func_wrap
        self.columns = table.columns
        for col in self.columns:
            col.table = self
        self._alias = table.alias

    def year_func_wrap(self, param):
        if self.need_year_func_wrap:
            return f"YEAR([{param}])"
        return f"[{param}]"

    def insert_temp_table(self, 
                          col: Column,
                          label:str,
                          val:int, 
                          less_val:int=None, 
                          wheres:list[Where] = None) -> None:
        if not self.tmp_table_name:
            raise PRISError("尚未設定暫存表名稱，請先設定tmp_table_name。")

        self._check_column(col)
        select_cols = self.outer_cols_to_string()
        
        col_expr = self.year_func_wrap(col.alias)
        cmd_base = (
            f"INSERT INTO {self.tmp_table_name} SELECT {select_cols}, '{self._escape_sql_string(str(label))}' "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE {col_expr}"
        )

        where_str = self.where_clause_to_string(wheres)

        if less_val is None:
            statement = f"{cmd_base} = {int(val)}{where_str}"
        else:
            # [Bug fix] 原本這裡多包了一層 [...] 變成 list,傳進 cursor.execute() 會 TypeError
            #           (年份區間如 "2020-2022" 時會踩到)
            statement = f"{cmd_base} > {int(val)} AND {col_expr} < {int(less_val)}{where_str}"
        SQLExecute.do_no_query(statement)

    def add_label_col(self, col_name):
        cmd = f"ALTER TABLE {self.tmp_table_name} ADD [{col_name}] varchar(32)"
        SQLExecute.do_no_query(cmd)


class ExtraColumnTable(Table):
    def __init__(self, full_name, alias:str = ""):
        super().__init__(full_name=full_name, alias=alias)
        self.extra_col_name : str = None
        self.extra_col_def : str = None
        self._shown_column :Column = None

    def set_extra_column_def(self, col_name: str, col_def:str):
        self.extra_col_name = col_name
        self.extra_col_def = col_def
        self._shown_column = Column(self, col_name)

    @property
    def shown_column(self):
        return self._shown_column

    ShownColumn = shown_column

    def extra_col_def_to_create_string(self)->str:
        if self.extra_col_name is None or self.extra_col_def is None:
            raise PRISError("Extra Column 不得為 Null")
        return f"CAST(NULL AS {self.extra_col_def}) AS [{self.alias}_{self.extra_col_name}]"
    
    def create_temp_table(self,  create_def: str | None = None) -> None:
        if not self.tmp_table_name:
            raise PRISError("尚未設定暫存表名稱，請先設定tmp_table_name。")

        extra_col_def_string = self.extra_col_def_to_create_string()
        outer_cols_string = self.outer_cols_to_string()
        cols_string = extra_col_def_string if not outer_cols_string else f"{extra_col_def_string}, {outer_cols_string}"

        command = f"SELECT TOP 0 {cols_string} INTO {self.tmp_table_name} FROM ({self.get_inner_select_clause()}) [{self.alias}]"
        
        SQLExecute.do_no_query(command)

    def insert_temp_table_eq_str(self, col: Column, val:str, wheres:list[Where] = None, distinct:bool = True):
        self.before_insert_check(col)

        distinct_str = self.get_distinct_str(distinct)
        select_cols = self.outer_cols_to_string()
        where_str = self.where_clause_to_string(wheres)

        
        str_cmd = (
            f"INSERT INTO {self.tmp_table_name} SELECT {distinct_str}N'{val}', {select_cols} "
            f"FROM ({self.get_inner_select_clause()}) [{self.alias}] WHERE 1=1{where_str}"
        )
        SQLExecute.do_no_query(str_cmd)

    # ------------------------------------------------------------------
    # [優化] 批次版 insert —— 取代「每個機構各執行一次 INSERT ... WHERE EXISTS(...)」
    # ------------------------------------------------------------------
    def insert_temp_table_by_patterns(
        self,
        key_patterns: list[tuple[str, str]],
        source: ITable,
        match_col: Column,
        bind_pairs: list[tuple[Column, Column]],
        use_like: bool,
        wheres: list[Where] | None = None,
        chunk_size: int = 300,
    ) -> int:
        """
        一次處理多個 (key, pattern),語意等同於對每個 key 各執行一次:

            INSERT INTO tmp
            SELECT DISTINCT N'key', <self.cols>
            FROM <self> WHERE EXISTS (
                SELECT * FROM <source> C
                WHERE C.<join_col> = <self>.<col> AND ... AND C.<match_col> LIKE|= N'pattern' AND <wheres>)

        改寫成「先把 source 與 (key,pattern) 清單 join 出 (key, 綁定欄位) 的集合,再 join 回 self」:
        每個 chunk 只掃描 source / self 各一次,而不是每個 key 掃描一次。

        - key_patterns : [(暫存表第一欄的值, 比對用 pattern)];同一個 key 可有多個 pattern(OR 關係)
        - source       : 提供比對的 JoinTable(例如 WOS_ORG ⨝ WOS_AUTHOR_ORG_RELATION)
        - match_col    : source 上被比對的欄位(例如 OrgName)
        - bind_pairs   : [(self 的欄位, source 的欄位)] 例如 (ISI_ID, ISI_ID),(AddressIndex, AddressIndex)...
        - use_like     : True → LIKE(pattern 含 %);False → =
        - wheres       : 套用在 source(別名 C)上的額外條件,例如 AuthorIndex = 1

        回傳實際執行的 SQL 數量。
        """
        if not self.tmp_table_name:
            raise PRISError("尚未設定暫存表名稱，請先設定tmp_table_name。")
        if not key_patterns:
            return 0
        if not bind_pairs:
            raise PRISError("bind_pairs 不得為空")

        op = "LIKE" if use_like else "="
        extra_col = f"[{self.alias}_{self.extra_col_name}]"
        own_cols = list(self.columns)                       # 固定順序,INSERT 欄位清單與 SELECT 清單共用
        insert_cols = ",".join([extra_col] + [f"[{c.alias}]" for c in own_cols])
        select_own = ",".join(f"[{self.alias}].[{c.alias}]" for c in own_cols)

        src_proj = ",".join(f"C.[{src.alias}] AS [b{i}]" for i, (_own, src) in enumerate(bind_pairs))
        on_clause = " AND ".join(
            f"X.[b{i}] = [{self.alias}].[{own.alias}]" for i, (own, _src) in enumerate(bind_pairs)
        )
        where_str = "".join(f" AND {w.to_sql(custom_table_name='C')}" for w in (wheres or ()) if w is not None)
        src_sql = source.get_inner_select_clause()
        own_sql = self.get_inner_select_clause()

        executed = 0
        for chunk in self._chunks(key_patterns, chunk_size):
            values = self.build_values_rows(chunk)
            cmd = (
                f"INSERT INTO {self.tmp_table_name} ({insert_cols}) "
                f"SELECT DISTINCT X.[k], {select_own} "
                f"FROM ({own_sql}) [{self.alias}] "
                f"INNER JOIN ("
                f"SELECT DISTINCT K.[k] AS [k], {src_proj} "
                f"FROM ({src_sql}) C "
                f"INNER JOIN (VALUES {values}) AS K([k],[p]) ON C.[{match_col.alias}] {op} K.[p] "
                f"WHERE 1 = 1{where_str}"
                f") X ON {on_clause}"
            )
            # commit=False: 由呼叫端(Subject.add_by_patterns)統一 commit
            SQLExecute.do_no_query(cmd, commit=False)
            executed += 1
        return executed
