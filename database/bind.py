from .column import Column
from .table import Table
from .sql import get_column_data_type


class Bind:
    column_type_not_support_collate = frozenset([
        "date",
        "int",
        "bigint",
        "smallint",
        "binary",
        "numeric",
        "varbinary",
        "datetime2",
    ])

    def __init__(self, subject_col: Column, table_col: Column, use_default_collate: bool = False, collate: str = None):
        self.subj_col = subject_col
        self.tbl_col = table_col
        self.use_default_collate = use_default_collate
        self.collate = collate
        self._no_collate_cache: bool | None = None

    def __str__(self):
        # Column.table.outmost 就是原本兩段 while 迴圈在做的事(往外找到最外層 Table)
        col_tbl = self.subj_col.table.outmost
        col2_tbl = self.tbl_col.table.outmost

        str_collate = ""
        if not self.column_not_support_collate():
            if self.use_default_collate:
                str_collate = " COLLATE DATABASE_DEFAULT"
            elif self.collate:
                str_collate = " COLLATE " + self.collate

        return f"[{col_tbl.alias}].[{self.subj_col.alias}] = [{col2_tbl.alias}].[{self.tbl_col.alias}]{str_collate}"

    def column_not_support_collate(self) -> bool:
        """
        [優化] 原本每次 __str__ 都會「開新連線」查兩次 INFORMATION_SCHEMA 且連線從不關閉
        (Query.select/count 每次都會 str(bind)),且用裸 except 把所有錯誤吃掉。
        現在: 結果快取在 Bind 實例上 + 全域型別快取(sql.get_column_data_type),
        使用既有連線,只在查詢失敗時才退回「視為支援 collate」,並留下訊息。
        """
        if self._no_collate_cache is not None:
            return self._no_collate_cache

        result = False
        try:
            for col in (self.subj_col, self.tbl_col):
                col_type = self.get_column_type(col)
                if col_type and col_type.lower() in self.column_type_not_support_collate:
                    result = True
                    break
        except Exception as e:      # 查不到型別不應中斷整份報表,但要讓人看得到
            print(f"[警告] 無法取得欄位型別 ({e!r}),假設可使用 COLLATE")
            return False            # 不快取失敗結果,下次再試

        self._no_collate_cache = result
        return result

    def get_column_type(self, col: Column) -> str | None:
        if not isinstance(col.table, Table):
            return None
        return get_column_data_type(col.table.db_name, col.table.table_name, col.name)
