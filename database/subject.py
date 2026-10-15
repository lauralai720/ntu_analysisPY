from .column import Column
from .table import Table,YTable
from .join_table import JoinTable,YJoinTable
from .where import Where
from .sql import SQLExecute
from exceptions import PRISError
from config import DEBUG
import itertools
import logging

# [Bug fix] 原本暫存表名稱用「initialize 當下的」Subject.no 組成,而 Subject.no 是在 __init__ 才 +1。
# 若先建立 A、B 兩個 Subject 再各自 initialize(),兩者會拿到同一個 #TEMPTBLn → 第二個 CREATE 失敗。
# 改為每個 Subject 在建構時領一個獨一無二的流水號。
_temp_seq = itertools.count(1)

class Subject:
    no = 0
    def __init__(self, table :Table, val_col : Column, shown_col = None):
        self._id = next(_temp_seq)
        self.table = table
        self._col = val_col
        self._shown_col = shown_col
        self.subj_vals : list[str] = []
        self.subj_vals_partial : list[str] = []
        self.initialized:bool = False
        self.select_all:bool= False # 不知道要做甚麼?

        if val_col.table.outmost is not table:
            raise PRISError(f"Column 的來源需為指定 Table '{table.alias}'")

        Subject.no += 1

    @property
    def name(self) -> str:
        return self.table.alias

    @property
    def column(self) -> Column:
        return self._shown_col if self._shown_col else self._col

    def initialize(self):
        self.temp_table_name = f"#TEMPTBL{self._id}"
        self.create_temp_table()
        SQLExecute.register_temp_table(self.temp_table_name)
        self.initialized = True

    Initialize = initialize

    def create_temp_table(self):
        self.table.tmp_table_name = self.temp_table_name
        self.table.create_temp_table()

    def drop_temp_table(self):
        """用完即丟,避免 tempdb 累積"""
        if getattr(self, "temp_table_name", None):
            SQLExecute.do_no_query(SQLExecute.drop_temp_sql(self.temp_table_name))
            SQLExecute.forget_temp_table(self.temp_table_name)

    def create_index(self, columns: list[Column], clustered: bool = True):
        """
        (選用) 暫存表填完後建索引。報表會對同一張暫存表 join 數十次,
        資料量大時可考慮;是否真的有幫助請用執行計畫/實測確認。
        """
        cols = ",".join(f"[{c.alias}]" for c in columns)
        kind = "CLUSTERED" if clustered else "NONCLUSTERED"
        idx = f"IX_{self.temp_table_name.lstrip('#')}"
        SQLExecute.do_no_query(f"CREATE {kind} INDEX {idx} ON {self.temp_table_name} ({cols})")

    def add(self,subj_val:str, wheres:list[Where] = None):
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")
        self.subj_vals.append(subj_val)
        self.table.insert_temp_table_eq_str(self._col, val=subj_val, wheres=wheres)

    def add_all(self,wheres:list[Where] = None):
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")
        self.select_all = True
        self.table.insert_temp_table(self._col, wheres=wheres)

    def add_range(self, subj_vals:list[str], wheres:list[Where] = None):
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")
        self.subj_vals.extend(subj_vals)
        self.table.insert_temp_table_list(self._col, val=subj_vals, wheres=wheres)

    def add_by_patterns(self, key_patterns: list[tuple[str, str]], source, match_col: Column,
                        bind_pairs: list[tuple[Column, Column]], use_like: bool,
                        wheres: list[Where] = None, chunk_size: int = 300) -> int:
        """
        [優化] 批次加入大量 (key, pattern)。只有 ExtraColumnTable 支援。
        不會動 subj_vals —— 因為 subj_vals 的順序會決定報表列的順序,
        請由呼叫端依「原本逐筆 add 的順序」自行 extend。
        回傳實際執行的 SQL 數。
        """
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")
        if not hasattr(self.table, "insert_temp_table_by_patterns"):
            raise PRISError("此 Subject 的 Table 不支援 insert_temp_table_by_patterns")
        n = self.table.insert_temp_table_by_patterns(
            key_patterns, source, match_col, bind_pairs, use_like, wheres, chunk_size)
        SQLExecute.commit()
        return n

    def add_partial(self,subj_val:str, keep_orig:bool, wheres:list[Where] = None, shown_val:str=None):
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")
        self.subj_vals_partial.append(subj_val)
        self.table.insert_temp_table_partial(self._col, val=subj_val, partial=True, keep_orig=keep_orig, wheres=wheres, shown_val=shown_val)

    # 去掉暫存表上重複的資料
    def distinct_temp_table(self):
        Subject.no += 1
        new_temp_name = f"#TEMPTBL{next(_temp_seq)}"

        if DEBUG:
            cnt = SQLExecute.do_count_query(f"SELECT COUNT(*) FROM {self.temp_table_name}")
            logging.debug(f"Row count of {self.temp_table_name} before distinct: {cnt}")

        select_cmd = f"SELECT DISTINCT * INTO {new_temp_name} FROM {self.temp_table_name}"
        SQLExecute.do_no_query(select_cmd)
        drop_cmd = f"DROP TABLE {self.temp_table_name}"
        SQLExecute.do_no_query(drop_cmd)
        SQLExecute.forget_temp_table(self.temp_table_name)

        self.temp_table_name = new_temp_name
        SQLExecute.register_temp_table(new_temp_name)

        if DEBUG:
            cnt = SQLExecute.do_count_query(f"SELECT COUNT(*) FROM {self.temp_table_name}")
            logging.debug(f"Row count of {self.temp_table_name} after distinct: {cnt}")

    Add = add
    AddPartial = add_partial
    AddRange = add_range
    AddAll = add_all
    DistinctTempTable = distinct_temp_table

YEARCOLUMN = "YEAR"
import re

class YearSubject(Subject):
    def __init__(self, table :Table, val_col : Column, need_year_func_wrap: bool = True):
        if isinstance(table, JoinTable):
            super().__init__(YJoinTable(table, need_year_func_wrap),val_col)
        else:
            super().__init__(YTable(table, need_year_func_wrap),val_col)

    def initialize(self):
        self.temp_table_name = f"#TEMPTBL{self._id}"
        self.create_temp_table()
        SQLExecute.register_temp_table(self.temp_table_name)

        self._col = Column(self.column)
        self.use_column_name = self.column.name
        self.column.set_name(YEARCOLUMN)
        self.initialized = True

    def create_temp_table(self):
        super().create_temp_table()
        if isinstance(self.table, (YTable,YJoinTable)):
            self.table.add_label_col(f"{self.column.table.alias}_{YEARCOLUMN}")

    def add(self,subj_val:str, wheres:list[Where] = None):
        if not self.initialized:
            raise PRISError("Suject 尚未初始化, 請先執行 Subject.Initialize()")

        self.column.set_name(self.use_column_name)

        period = re.compile(r"\d{4}-\d{4}")
        single = re.compile(r"\d{4}")
        if period.match(subj_val):
            year_list = subj_val.split('-')
            from_year = int(year_list[0]) - 1
            to_year = int(year_list[1]) + 1 
            if isinstance(self.table, (YTable,YJoinTable)):
                self.table.insert_temp_table(self.column, subj_val, from_year, to_year, wheres=wheres)
        elif single.match(subj_val):
            year = int(subj_val)
            if isinstance(self.table, (YTable,YJoinTable)):
                self.table.insert_temp_table(self.column, subj_val, year, wheres=wheres)            
        else:
            raise PRISError("年代格式不正確, 只接受 YYYY 與 YYYY-YYYY 兩種格式")
        
        self.subj_vals.append(subj_val)
        self.column.set_name(YEARCOLUMN)

    def add_all(self,wheres:list[Where] = None):
        raise PRISError("YearSubject 無法使用 add_all()")

    def add_range(self, subj_vals:list[str], wheres:list[Where] = None):
        raise PRISError("YearSubject 無法使用 add_range()")

    def add_partial(self,subj_val:str, keep_orig:bool, wheres:list[Where] = None, shown_val:str=None):
        raise PRISError("YearSubject 無法使用 add_partial()")

    Initialize = initialize