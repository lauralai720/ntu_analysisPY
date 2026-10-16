from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .sql import OpType, SQLOperator

if TYPE_CHECKING:
    from .column import Column
    from .subject import Subject
    from .table import Table
    from .join_table import JoinTable

def _quote(value: Any, unicode: bool = True) -> str:
    prefix = "N" if unicode else ""
    return f"{prefix}'{str(value).replace(chr(39), chr(39) * 2)}'" #replace("'", "''")

@dataclass
class _WhereObject:
    kind: str
    values: dict[str, Any]

class Where:
    def __init__(self, obj: _WhereObject):
        self._obj = obj

    def to_sql(self, use_raw_column_name: bool = False,
               custom_table_name: str | None = None) -> str:
        v = self._obj.values

        def name(column: "Column") -> str:
            if use_raw_column_name:
                return column.name
            if custom_table_name is not None:
                return f"{custom_table_name}.[{column.alias}]"
            return f"[{column.table.outmost.alias}].[{column.alias}]"

        kind = self._obj.kind
        if kind == "column":
            return f"{name(v['c1'])} {SQLOperator(v['op'])} {name(v['c2'])}"
        if kind == "const":
            return f"{_quote(v['c1'])} {SQLOperator(v['op'])} {_quote(v['c2'])}"
        if kind == "column_to_const":
            return f"{name(v['c1'])} {SQLOperator(v['op'])} {_quote(v['c2'])}"
        if kind == "null":
            return f"{name(v['column'])} {SQLOperator(v['op'])} NULL"
        if kind == "multi_const":
            values = ", ".join(_quote(item, unicode=False) for item in v["values"])
            return f"{name(v['column'])} {SQLOperator(v['op'])} ({values})"
        if kind == "func_const":
            return f"{v['func'].format(name(v['column']))} {SQLOperator(v['op'])} {_quote(v['value'])}"
        if kind == "func_multi":
            values = ", ".join(_quote(item, unicode=False) for item in v["values"])
            return f"{v['func'].format(name(v['column']))} IN ({values})"
        if kind == "operated":
            return f"{name(v['column'])} {SQLOperator(v['op1'])} {v['value1']} {SQLOperator(v['op2'])} {v['value2']}"
        if kind == "multiple":
            wheres = v["wheres"]
            if not wheres:
                return "1 = 1"
            separator = f" {SQLOperator(v['op'])} "
            return "(" + separator.join(where.to_sql(custom_table_name=custom_table_name) for where in wheres) + ")"
        if kind == "subject":
            if v["op"] not in (OpType.IN, OpType.NOT_IN):
                raise ValueError("Subject 物件只支援 OpType.In 與 OpType.NotIn 操作元")
            return f"{name(v['c1'])} {SQLOperator(v['op'])} (SELECT [{v['c2'].alias}] FROM [{v['subject'].temp_table_name}])"
        if kind == "table_column":
            value = v["value"]
            if isinstance(value, int):
                rendered = str(value)
            elif isinstance(value, (list, tuple, set)):
                rendered = "(" + ",".join(map(str, value)) + ")"
            else:
                rendered = _quote(value)
            collate = f" COLLATE {v['collate']}" if v["collate"] else ""
            select_column = v["c_alias"] or v["c1"].name
            return (f"{name(v['c1'])} IN (SELECT DISTINCT [{select_column}]{collate} "
                    f"FROM {v['table'].full_name} WHERE {v['c2'].name} "
                    f"{SQLOperator(v['op'])} {rendered})")
        if kind == "join_column":
            sub_where = "" if v["where"] is None else f" WHERE {v['where'].to_sql(custom_table_name='C')}"
            return (f"{name(v['c1'])} IN (SELECT DISTINCT C.[{v['c2'].alias}] "
                    f"FROM ({v['table'].get_inner_select_clause()}) C{sub_where})")
        if kind == "join_columns":
            if len(v["columns"]) != len(v["join_columns"]):
                raise ValueError("Join 之欄位個數不相等")
            terms = [f"C.[{joined.alias}] = {name(column)}"
                     for column, joined in zip(v["columns"], v["join_columns"])]
            if v["where"] is not None:
                terms.append(v["where"].to_sql(custom_table_name="C"))
            return f"EXISTS (SELECT DISTINCT * FROM ({v['table'].get_inner_select_clause()}) C WHERE {' AND '.join(terms)})"
        if kind == "table_group":
            sub_where = "" if v["where"] is None else f" WHERE {v['where'].to_sql(use_raw_column_name=True)}"
            distinct = "DISTINCT " if v["distinct"] else ""
            aggregate = v["func"].format(f"{distinct}{v['c2'].name}")
            return (f"{name(v['c1'])} IN (SELECT DISTINCT [{v['c1'].name}] FROM {v['table'].full_name}"
                    f"{sub_where} GROUP BY [{v['c1'].name}] HAVING {aggregate} {SQLOperator(v['op'])} {v['value']})")
        if kind == "join_group":
            sub_where = "" if v["where"] is None else f" WHERE {v['where'].to_sql(custom_table_name='C')}"
            distinct = "DISTINCT " if v["distinct"] else ""
            aggregate = v["func"].format(f"{distinct}C.[{v['c3'].alias}]")
            return (f"{name(v['c1'])} IN (SELECT DISTINCT C.[{v['c2'].alias}] "
                    f"FROM ({v['table'].get_inner_select_clause()}) C{sub_where} "
                    f"GROUP BY C.[{v['c2'].alias}] HAVING {aggregate} {SQLOperator(v['op'])} {v['value']})")
        raise RuntimeError(f"Unknown where type: {kind}")
    
    def __str__(self) -> str:
        return self.to_sql()

    ## c1 <op> c2. [OrgSerial] = [OrgID]
    @classmethod
    def column(cls, c1: "Column", op: OpType, c2: "Column") -> "Where":
        return cls(_WhereObject("column", locals()))

    ## c1 <op> c2，目前未使用到
    @classmethod
    def const(cls, c1: str, op: OpType, c2: str) -> "Where":
        return cls(_WhereObject("const", locals()))

    ## c1 <op> c2，ex. [OrgSerial] = 'TWU000001'
    @classmethod
    def column_to_const(cls, c1: "Column", op: OpType, c2: str) -> "Where":
        return cls(_WhereObject("column_to_const", locals()))

    ## column <op> NULL，ex. [OrgSerial] = NULL
    @classmethod
    def null(cls, column: "Column", op: OpType) -> "Where":
        return cls(_WhereObject("null", {"column": column, "op": op}))

    ## column IN (",".join(values))
    @classmethod
    def column_val_in_multi_const(cls, column: "Column", op: OpType,
                                  values: list[str]) -> "Where":
        return cls(_WhereObject("multi_const", {"column": column, "op": op, "values": list(values)}))

    ## 目前未使用到
    @classmethod
    def func_column_to_const(cls, func: str, column: "Column", op: OpType,
                             value: str) -> "Where":
        return cls(_WhereObject("func_const", {"func": func, "column": column, "op": op, "value": value}))

    ## 目前未使用到
    @classmethod
    def func_column_val_in_multi_const(cls, func: str, column: "Column", op: OpType,
                                       values: list[str]) -> "Where":
        return cls(_WhereObject("func_multi", {"func": func, "column": column, "op": op, "values": list(values)}))

    # column <op1> value1 <op2> value2
    @classmethod
    def operated_column_to_const(cls, column: "Column", op1: OpType, value1: str,
                                 op2: OpType, value2: str) -> "Where":
        return cls(_WhereObject("operated", {
            "column": column, "op1": op1, "value1": value1, "op2": op2, "value2": value2,
        }))

    @classmethod
    def multiple_where(cls, wheres: list["Where"], op: OpType) -> "Where":
        return cls(_WhereObject("multiple", {"wheres": list(wheres), "op": op}))

    @classmethod
    def column_val_in_subject(cls, c1: "Column", op: OpType, subject: "Subject",
                              c2: "Column") -> "Where":
        return cls(_WhereObject("subject", {"c1": c1, "op": op, "subject": subject, "c2": c2}))

    @classmethod
    def column_val_in_table_column(cls, c1: "Column", table: "Table", c2: "Column",
                                   op: OpType, value: Any, c_alias: str | None = None,
                                   collate: str | None = None) -> "Where":
        return cls(_WhereObject("table_column", locals()))

    @classmethod
    def column_val_in_join_table_column(cls, c1: "Column", c2: "Column", table: "JoinTable",
                                        where: "Where | None" = None, distinct: bool = False) -> "Where":
        return cls(_WhereObject("join_column", locals()))

    @classmethod
    def column_val_in_join_table_column_multiple(cls, columns: list["Column"], join_columns: list["Column"],
                                                 table: "JoinTable", where: "Where | None" = None,
                                                 distinct: bool = False) -> "Where":
        return cls(_WhereObject("join_columns", locals()))

    @classmethod
    def column_val_in_table_group_by_column(cls, c1: "Column", c2: "Column", table: "Table",
                                            func: str, op: OpType, value: int,
                                            where: "Where | None" = None,
                                            distinct: bool = False) -> "Where":
        return cls(_WhereObject("table_group", locals()))

    @classmethod
    def column_val_in_join_table_group_by_column(cls, c1: "Column", c2: "Column", table: "JoinTable",
                                                 c3: "Column", func: str, op: OpType, value: int,
                                                 where: "Where | None" = None,
                                                 distinct: bool = False) -> "Where":
        return cls(_WhereObject("join_group", locals()))