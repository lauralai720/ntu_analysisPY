import pandas as pd

from .table import ITable
from .subject import Subject
from .bind import Bind
from .column import Column
from .where import Where
from .sql import SQLExecute

class Query:
    def __init__(self, table:"ITable"):
        self.table = table
        self._subject1:Subject = None
        self._subject2:Subject = None
        self._subject3:Subject = None
        self._bind1:list[Bind] = None
        self._bind2:list[Bind] = None
        self._bind3:list[Bind] = None

    def set_subject1(self, subj: Subject, binds:Bind|list[Bind]):
        self._subject1 = subj
        if isinstance(binds, Bind):
            binds = [binds]
        self._bind1 = binds

    def set_subject2(self, subj: Subject, binds:Bind|list[Bind]):
        self._subject2 = subj
        if isinstance(binds, Bind):
            binds = [binds]
        self._bind2 = binds

    def set_subject3(self, subj: Subject, binds:Bind|list[Bind]):
        self._subject3 = subj
        if isinstance(binds, Bind):
            binds = [binds]
        self._bind3 = binds

    def select(self, 
               order_by : list[Column], 
               distinct :bool = False, 
               wheres: list[Where] = None, 
               keep_cols: list[Column] = None, 
               remove_subj_col:bool = False
            ) -> pd.DataFrame:
        
        distinct_str = "DISTINCT " if distinct else ""
        final_keep_cols = []
        if not remove_subj_col:
            if self._subject1 is not None:
                final_keep_cols.append(self._subject1.column)
            if self._subject2 is not None:
                final_keep_cols.append(self._subject2.column)    
            if self._subject3 is not None:
                final_keep_cols.append(self._subject3.column) 

        final_keep_cols.extend(self.table.get_columns() if keep_cols is None else keep_cols)

        cols_str = self.cols_to_string(final_keep_cols)

        cmd_str = f"SELECT {distinct_str}{cols_str} FROM ({self.table.get_inner_select_clause()}) [{self.table.alias}]"

        if self._subject1 is not None:
            cmd_str += f" INNER JOIN {self._subject1.temp_table_name} [{self._subject1.name}] ON {self.binds_to_string(self._bind1)}"
        if self._subject2 is not None:
            cmd_str += f" INNER JOIN {self._subject2.temp_table_name} [{self._subject2.name}] ON {self.binds_to_string(self._bind2)}"
        if self._subject3 is not None:
            cmd_str += f" INNER JOIN {self._subject3.temp_table_name} [{self._subject3.name}] ON {self.binds_to_string(self._bind3)}"

        if wheres is not None and len(wheres)>0:
            cmd_str += " WHERE "
            wheres_str = [str(w) for w in wheres if w is not None]
            cmd_str += " AND ".join(wheres_str)

        if order_by is not None:
            cmd_str += " ORDER BY "
            cmd_str += ",".join([f" [{ob_col.table.outmost.alias}].[{ob_col.alias}]" for ob_col in order_by])
        elif (self._subject1 is not None or self._subject2 is not None or self._subject3 is not None) and not remove_subj_col:
            flag = False
            cmd_str += " ORDER BY"
            if self._subject1 is not None and any(c == self._subject1.column for c in final_keep_cols):
                cmd_str += f" [{self._subject1.column.table.outmost.alias}].[{self._subject1.column.alias}]"
                flag = True
            if self._subject2 is not None and any(c == self._subject2.column for c in final_keep_cols):
                cmd_str += (" ," if flag else "") + f" [{self._subject2.column.table.outmost.alias}].[{self._subject2.column.alias}]"
                flag = True
            if self._subject3 is not None and any(c == self._subject3.column for c in final_keep_cols):
                cmd_str += (" ," if flag else "") + f" [{self._subject3.column.table.outmost.alias}].[{self._subject3.column.alias}]"

        
        df = SQLExecute.query(cmd_str)

        return df

    def count(self,
              count_column:Column,
              distinct:bool = False, 
              order_by_result :bool = False, 
              order_by : list[Column] = None, 
              wheres: list[Where] = None, 
              keep_cols: list[Column] = None, 
              remove_subj_col:bool = False, 
              result_column_name:str = "Result", 
              count_func:str = "COUNT") -> pd.DataFrame:

        distinct_str = "DISTINCT " if distinct else ""
        final_keep_cols = []
        if not remove_subj_col:
            if self._subject1 is not None:
                final_keep_cols.append(self._subject1.column)
            if self._subject2 is not None:
                final_keep_cols.append(self._subject2.column)    
            if self._subject3 is not None:
                final_keep_cols.append(self._subject3.column)

        final_keep_cols.extend(self.table.get_columns() if keep_cols is None else keep_cols)

        cols_except_count_col = [col for col in final_keep_cols if col != count_column]
        cols_str = self.cols_to_string(cols_except_count_col)
        delimeter = ", " if cols_str else ""

        cmd_str = ( 
            f"SELECT {cols_str}{delimeter}{count_func} ({distinct_str}[{count_column.table.outmost.alias}].[{count_column.alias}]) AS [{result_column_name}] "
            f"FROM ({self.table.get_inner_select_clause()}) [{self.table.alias}]"
        )

        if self._subject1 is not None:
            cmd_str += f" INNER JOIN {self._subject1.temp_table_name} [{self._subject1.name}] ON {self.binds_to_string(self._bind1)}"
        if self._subject2 is not None:
            cmd_str += f" INNER JOIN {self._subject2.temp_table_name} [{self._subject2.name}] ON {self.binds_to_string(self._bind2)}"
        if self._subject3 is not None:
            cmd_str += f" INNER JOIN {self._subject3.temp_table_name} [{self._subject3.name}] ON {self.binds_to_string(self._bind3)}"

        if wheres is not None and len(wheres)>0:
            cmd_str += " WHERE "
            wheres_str = [str(w) for w in wheres if w is not None]
            cmd_str += " AND ".join(wheres_str)

        if cols_str:
            cmd_str += f" GROUP BY {cols_str}"

        if order_by is not None:
            cmd_str += " ORDER BY"
            cmd_str += ",".join([f" [{ob_col.table.outmost.alias}].[{ob_col.alias}]" for ob_col in order_by])

            if order_by_result:
                cmd_str += f", [{result_column_name}] DESC"
        elif order_by_result:
            cmd_str += f" ORDER BY [{result_column_name}] DESC"
        elif (self._subject1 is not None or self._subject2 is not None or self._subject3 is not None) and not remove_subj_col:
            flag = False
            cmd_str += " ORDER BY"
            if self._subject1 is not None and any(c == self._subject1.column for c in final_keep_cols):
                cmd_str += f" [{self._subject1.column.table.outmost.alias}].[{self._subject1.column.alias}]"
                flag = True
            if self._subject2 is not None and any(c == self._subject2.column for c in final_keep_cols):
                cmd_str += (" ," if flag else "") + f" [{self._subject2.column.table.outmost.alias}].[{self._subject2.column.alias}]"
                flag = True
            if self._subject3 is not None and any(c == self._subject3.column for c in final_keep_cols):
                cmd_str += (" ," if flag else "") + f" [{self._subject3.column.table.outmost.alias}].[{self._subject3.column.alias}]"
        
        df = SQLExecute.query(cmd_str)

        return df
    
    def binds_to_string(self, binds:list[Bind])->str:
        ret = ""
        if binds:
            ret = " AND ".join([str(b) for b in binds])
        return ret
    
    def cols_to_string(self, cols : list[Column]) -> str:
        ret = ""
        if cols:
            ret = ",".join([f"[{col.table.outmost.alias}].[{col.alias}]" for col in cols])

        return ret