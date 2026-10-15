"""
DataAccessLayer —— 集中管理所有跟 DLL(.NET)溝通的邏輯。

設計原則:
- 這是整個專案唯一需要知道「.NET / pythonnet / DLL」這些細節的地方。
- main.py 跟其他業務邏輯檔案,只需要 import 這個 class,呼叫它提供的方法,
  完全不需要知道 clr.AddReference、DataTable 這些底層細節。
- 對外的方法一律回傳 pandas.DataFrame 或 Python 原生型態。
- 未來基底 DLL 專案 Python 化之後,只需要重寫這個檔案內部的實作,
  對外的方法簽名維持不變,呼叫端完全不用修改。
"""
import pandas as pd

from database import *

class DataAccessLayer:
    def __init__(self):

        self.JOINTYPE = JoinType
        self.OPTYPE = OpType

    def create_column(self, *args, **kwargs):
        return Column(*args, **kwargs)

    def create_subject(self, *args, **kwargs):
        return Subject(*args, **kwargs)

    def create_join_table(self, *args, **kwargs):
        return JoinTable(*args, **kwargs)
    
    def create_where(self, *args, **kwargs):
        return Where(*args, **kwargs)

    def create_where_column(self, c1, op, c2):
        return Where.column(c1, op, c2)
    
    def create_where_column_to_const(self, c1, op, c2):
        return Where.column_to_const(c1, op, c2)
    
    def create_where_null(self, c1, op,):
        return Where.null(c1, op)
    
    def create_where_multiple(self,wlist,op):
        return Where.multiple_where(wlist, op)
    
    def create_where_column_val_in_join_table_column_multiple(self, clist1,clist2,join_table,where = None, distinct:bool=False):
        return Where.column_val_in_join_table_column_multiple(clist1, clist2, join_table, where, distinct)
    
    def create_where_operated_column_to_const(self, c, op1, v1, op2, v2):
        return Where.operated_column_to_const(c, op1, v1, op2, v2)
        
    def create_where_column_val_in_subject(self,c1, op, s, c2):
        return Where.column_val_in_subject(c1, op, s, c2)

    def create_query(self, *args, **kwargs):
        return Query(*args, **kwargs)
    
    def create_table(self, *args, **kwargs):
        return Table(*args, **kwargs)
    
    def create_join_on(self, *args, **kwargs):
        return JoinOn(*args, **kwargs)

    def create_bind(self, *args, **kwargs):
        return Bind(*args, **kwargs)

    def create_extra_column_table(self, *args, **kwargs):
        return ExtraColumnTable(*args, **kwargs)
    
    def create_year_subject(self, *args, **kwargs):
        return YearSubject(*args, **kwargs)

    def create_year_table(self, *args, **kwargs):
        return YTable(*args, **kwargs)

    def query_2d_raw(self, cmd: str) -> list[list[str]]:
        """回傳最原始的 list[list[str]],不做任何轉換,適合要逐筆組成自訂物件的情境"""
        result = SQLExecute.query_2d_raw(cmd)
        return result

    def query(self, cmd:str) -> pd.DataFrame:
        df = SQLExecute.query(cmd)
        return df
    
    def do_no_query(self, cmd:str):
        SQLExecute.do_no_query(cmd) #, conn_ref[0])

