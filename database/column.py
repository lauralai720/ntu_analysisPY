from exceptions import PRISError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .table import ITable


class Column:
    def __init__(self, table: "ITable | Column", column: str | None = None,
                 func: str | None = None, concat: list[str] | None = None,
                 col_minor: "Column | None" = None):
        if isinstance(table, Column):
            source = table
            self.table = source.table
            self.name = source.name
            self.sql_func = source.sql_func
            self.col_major = source.col_major
            self.col_minor = source.col_minor
            self.concat = source.concat
            return
        
        if column is None:
            raise PRISError("Column name cannot be None or empty.")
        
        self.table = table
        self.name = column
        self.sql_func = func
        self.col_major: Column | None = None
        self.col_minor: Column | None = col_minor
        self.concat = tuple(concat) if concat is not None else None

    @classmethod
    def coalesce(cls, table: "ITable", major: "Column", minor: "Column",
                 name: str) -> "Column":
        column = cls(table, name)
        column.col_major = major
        column.col_minor = minor
        return column

    @property
    def alias(self) -> str:
        return f"{self.table.alias}_{self.name}"

    def get_table(self) -> "ITable":
        return self.table

    def set_name(self, name: str) -> None:
        self.name = name

    def to_inner_string(self) -> str:
        if self.concat is not None:
            cols = "+ '-' +".join(
                f"CAST([{self.table.alias}].[{name}] AS varchar)"
                for name in self.concat
            )
            return f"{cols} AS [{self.alias}]"
        if self.sql_func is not None:
            return f"{self.sql_func}([{self.table.alias}].[{self.name}]) AS [{self.alias}]"
        if self.col_major is not None and self.col_minor is not None:
            return f"ISNULL([{self.col_major.alias}], [{self.col_minor.alias}]) AS [{self.alias}]"
        return f"[{self.table.alias}].[{self.name}] AS [{self.alias}]"

    def to_outer_string(self, source_table_name: str) -> str:
        return f"[{source_table_name}].[{self.alias}] AS [{self.alias}]"


class CastColumn(Column):
    def __init__(self, casts: list[Column], table: "ITable", column: str,
                 set_db_default_collate: bool = False):
        super().__init__(table, column)
        self.casts = tuple(casts)
        self.set_db_default_collate = set_db_default_collate

    def to_inner_string(self) -> str:
        return "NULL AS DUMMY"

    def to_outer_string(self, source_table_name: str) -> str:
        collate = " COLLATE DATABASE_DEFAULT" if self.set_db_default_collate else ""
        columns = "+ '-' +".join(
            f"[{source_table_name}].[{column.alias}]{collate}"
            for column in self.casts
        )
        return f"{columns} AS [{self.alias}]"
