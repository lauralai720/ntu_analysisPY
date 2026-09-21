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
from pathlib import Path
import pandas as pd
import dotnet_setup

DLL_DIR = Path(__file__).parent / "dlls"

from components.subjects import Subjects

class DataAccessLayer:
    def __init__(self):
        # 整個專案的 .NET 初始化,集中在這裡做,只會真正執行一次
        dotnet_setup.init_dotnet(runtime="netfx")
        self._setup_dll_references()
        

    def _setup_dll_references(self):
        """集中管理所有 clr.AddReference,新增 DLL 時只需要改這裡"""
        import sys

        import clr

        if str(DLL_DIR) not in sys.path:
            sys.path.append(str(DLL_DIR))

        #clr.AddReference("System")  # 確保基礎 System 核心有被載入
        clr.AddReference("System.Data")
        clr.AddReference("PRISUtilityKit")  # 依實際 DLL 檔名調整

        from PRISUtilityKit.DBAL.Cls import JoinType as DllJoinType, OpType as DllOpType
        
        self.JOINTYPE = DllJoinType
        self.OPTYPE = DllOpType

    def to_csharp_list(self, py_list: list, dotnet_type):
        """轉換成 .NET 的 List<T>(對應 C# 的 List<T>)"""
        from System.Collections.Generic import List

        dotnet_list = List[dotnet_type]()
        for item in py_list:
            dotnet_list.Add(item)
        return dotnet_list


    def to_csharp_array(self, py_list: list):
        import System
        """
        將任何包含 .NET 物件的 Python list，自動轉換為對應強型別的 System.Array
        """
        # 防呆機制：如果傳入空列表，預設建立一個 Object 類型的空陣列
        if not py_list:
            return System.Array[System.Object](0)
        
        # 1. 自動動態取得清單中第一個物件的 .NET 型別 (Type)
        first_item = py_list[0]
        
        # 如果是 .NET 物件，它會有 GetType() 方法
        if hasattr(first_item, "GetType"):
            dotnet_type = first_item.GetType()
        elif isinstance(first_item, str):
            dotnet_type = System.String
        elif isinstance(first_item, bool):  # 要放在 int 判斷之前,因為 bool 是 int 的子類別
            dotnet_type = System.Boolean
        elif isinstance(first_item, int):
            dotnet_type = System.Int32
        elif isinstance(first_item, float):
            dotnet_type = System.Double
        else:
            dotnet_type = System.Object

            
        # 2. 利用 .NET 反射動態建立該型別的陣列
        # 語法：System.Array.CreateInstance(型別, 長度)
        csharp_array = System.Array.CreateInstance(dotnet_type, len(py_list))
        
        # 3. 將 Python list 的資料依序填入 .NET 陣列
        for index, item in enumerate(py_list):
            csharp_array[index] = item
            
        return csharp_array

    def to_where_array(self, where_list: list):
        """把 list[Where] 轉成 Where[]"""
        from PRISUtilityKit.DBAL.Cls import Where
        import System

        array = System.Array.CreateInstance(Where, len(where_list))
        for index, item in enumerate(where_list):
            array[index] = item
        return array
    # ------------------------------------------------------------------
    # 對外提供的型別 (業務邏輯層只呼叫這一層,不要自己碰 DLL)
    # ------------------------------------------------------------------
    """
    情境一:業務邏輯層要做 isinstance 判斷

    B2Type = dal.get_b2_type()
    if isinstance(some_obj, B2Type):
        ...

    情境二:業務邏輯層要動態決定建立哪種型別(比如依照條件,有時候建立 B1、有時候建立 B2)

    type_map = {"code1": dal.get_b1_type(), "code2": dal.get_b2_type()}
    target_type = type_map[some_condition]
    instance = target_type(...)
    """
    # def get_column_type(self):
    #     """提供 Column 這個 DLL 型別,給需要建立/操作它的業務邏輯層使用"""
    #     from PRISUtilityKit.DBAL.Cls import Column
    #     return Column
    def get_DB(self):
        from PRISUtilityKit.DBAL.Cls import DB
        Conn = DB.GetShareConnection()
        return Conn
    
    def create_column(self, *args, **kwargs):
        """更常見的做法:不直接暴露型別本身,而是提供『建立這個型別實例』的方法"""
        from PRISUtilityKit.DBAL.Cls import Column
        return Column(*args, **kwargs)

    def create_subject(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import Subject
        return Subject(*args, **kwargs)

    def create_join_table(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import JoinTable
        return JoinTable(*args, **kwargs)
    
    def create_where(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where(*args, **kwargs)

    def create_where_column(self, c1, op, c2):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where.Column(c1, op, c2)
    
    def create_where_column_to_const(self, c1, op, c2):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where.ColumnToConst(c1, op, c2)
    
    def create_where_null(self, c1, op,):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where.Null(c1, op)
    
    def create_where_multiple(self,wlist,op):
        from PRISUtilityKit.DBAL.Cls import Where
        where_arr = self.to_csharp_array(wlist)
        return Where.MultipleWhere(where_arr, op)
    
    def create_where_column_val_in_join_table_column_multiple(self, clist1,clist2,join_table,where = None, distinct:bool=False):
        from PRISUtilityKit.DBAL.Cls import Where, Column
        c1_list = self.to_csharp_list(clist1, Column)
        c2_list = self.to_csharp_list(clist2, Column)
        return Where.ColumnValInJoinTableColumnMultiple(c1_list, c2_list, join_table, where, distinct)
    
    def create_where_operated_column_to_const(self, c, op1, v1, op2, v2):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where.OperatedColumnToConst(c, op1, v1, op2, v2)
        
    def create_where_column_val_in_subject(self,c1, op, s, c2):
        from PRISUtilityKit.DBAL.Cls import Where
        return Where.ColumnValInSubject(c1, op, s, c2)

    def create_query(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import Query
        return Query(*args, **kwargs)
    
    def create_table(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import Table
        return Table(*args, **kwargs)
    
    def create_join_on(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import JoinOn
        return JoinOn(*args, **kwargs)

    def create_bind(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import Bind
        return Bind(*args, **kwargs)

    def create_extra_column_table(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import ExtraColumnTable
        return ExtraColumnTable(*args, **kwargs)

    def create_extra_column_table(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import ExtraColumnTable
        return ExtraColumnTable(*args, **kwargs)
    
    def create_year_subject(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import YearSubject
        return YearSubject(*args, **kwargs)

    def create_year_table(self, *args, **kwargs):
        from PRISUtilityKit.DBAL.Cls import YTable
        return YTable(*args, **kwargs)
    # ------------------------------------------------------------------
    # 對外提供的方法(業務邏輯層只呼叫這一層,不要自己碰 DLL)
    # ------------------------------------------------------------------

    def set_connection(self, param1: str, param2: str, param3: str) -> bool:
        """對應 DB.Set(...),設定/測試連線"""
        from PRISUtilityKit.DBAL.Cls import DB
        from System import ValueTuple

        param = ValueTuple.Create(param1, param2, param3)
        return bool(DB.Set(param))

    def query_2d_raw(self, cmd: str) -> list[list[str]]:
        """回傳最原始的 list[list[str]],不做任何轉換,適合要逐筆組成自訂物件的情境"""
        from PRISUtilityKit.DBAL.Cls import SQLExecute
        result = SQLExecute.DoQuery2D(cmd)
        if result is None:
            return []
        return [list(row) for row in result]

    def query_2d(self, cmd: str, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        """對應 SQLExecute.DoQuery2D(),回傳 List<List<string>>"""
        from PRISUtilityKit.DBAL.Cls import SQLExecute

        result = SQLExecute.DoQuery2D(cmd)
        return self._list2d_to_dataframe(result, dtype_map)

    def query(self, cmd:str) -> "DataTable":
        import clr
        from System.Data.SqlClient import SqlConnection
        from PRISUtilityKit.DBAL.Cls import DB,SQLExecute  # 依實際 namespace/method 調整

        Conn = DB.GetShareConnection()
        conn_ref = [Conn]  
        dt = SQLExecute.DoQuery(cmd, conn_ref[0])

        return dt
    
    def do_no_query(self, cmd:str):
        from PRISUtilityKit.DBAL.Cls import DB,SQLExecute  # 依實際 namespace/method 調整
        Conn = DB.GetShareConnection()
        conn_ref = [Conn]  
        SQLExecute.DoNonQuery(cmd, conn_ref[0])

    def query_pd(self, cmd:str, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        dt = self.query(cmd)
        return self.datatable_to_dataframe(dt, dtype_map)


    def a02_sumup_calculate(self, dt : "DataTable", dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        """對應某個回傳 System.Data.DataTable 的 DLL 方法"""
        from PRISUtilityKit.DBAL.Module import A02_SumUp

        dt = A02_SumUp.Calculate(dt)
        return self.datatable_to_dataframe(dt, dtype_map)

    # 實驗，原本是要傳c# 的 DataTable，先改用pd.DataFrame，在這邊轉成DataTable
    def b22_ranking_calculate(self, df : pd.DataFrame, analysis_idx:int = 0, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        from PRISUtilityKit.DBAL.Module import B22_Ranking
        dt = self._dataframe_to_datatable(df = df)
        dt = B22_Ranking.Calculate(dt, analysis_idx)
        return self.datatable_to_dataframe(dt, dtype_map)

    def a08_cntavg_calculate(self, df : pd.DataFrame, decimals:int = -1, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        from PRISUtilityKit.DBAL.Module import A08_CntAvg
        dt = self._dataframe_to_datatable(df = df)
        dt = A08_CntAvg.Calculate(dt, decimals)
        return self.datatable_to_dataframe(dt, dtype_map)

    def a08_cntavg_calculate_join(self, df_1 : pd.DataFrame,df_2 : pd.DataFrame, decimals:int = -1, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        from PRISUtilityKit.DBAL.Module import A08_CntAvg
        from PRISUtilityKit.DBAL.Lib import Utils
        dt_1 = self._dataframe_to_datatable(df = df_1)
        dt_2 = self._dataframe_to_datatable(df = df_2)
        dt = A08_CntAvg.Calculate(Utils.Join(dt_1, dt_2), decimals)
        return self.datatable_to_dataframe(dt, dtype_map)

    def growth_rate_calculate(self, df : pd.DataFrame, year_idx:int, ori_years : list[str], per_year_func, use_percentage: bool = True, na_val_notation=None) -> pd.DataFrame:
        from PRISUtilityKit.DBAL.Module import GrowthRate
        from System import Func
        dt = self._dataframe_to_datatable(df = df)
        ori_years_cs = self.to_csharp_list(ori_years, str)
        per_year_func_cs = Func[str, str](per_year_func)
        dt = GrowthRate.Calculate(dt, year_idx, ori_years_cs, per_year_func_cs, use_percentage, na_val_notation)
        return self.datatable_to_dataframe(dt)
    # ------------------------------------------------------------------
    # 一些靜態的轉換方法，但有可能用到dll的型別
    # ------------------------------------------------------------------
    @staticmethod
    def get_binds(
        bind_subject1_column,
        bind_subject2_column,
        bind_year_column,
        subjects : Subjects,
        subject1_bind_column_name: str,
        subject2_bind_column_name: str,
        subject_year_bind_column_name: str,
        extra_bind1_columns: dict | None = None,
        extra_bind2_columns: dict | None = None,
        extra_bind3_columns: dict | None = None,
    ):
        """
        對應 GetBinds(...),回傳 (Bind[] Bind1, Bind[] Bind2, Bind[] Bind3)
        """
        from PRISUtilityKit.DBAL.Cls import Bind  # 依實際 namespace 調整

        bind1 = None
        if subjects.subject1 is not None:
            bind1 = [Bind(subjects.subj1BindCol[subject1_bind_column_name], bind_subject1_column)]
            if extra_bind1_columns is not None:
                for key, value in extra_bind1_columns.items():
                    if key in subjects.subj1BindCol:
                        bind1.append(Bind(subjects.subj1BindCol[key], value))

        bind2 = None
        if subjects.subject2 is not None:
            bind2 = [Bind(subjects.subj2BindCol[subject2_bind_column_name], bind_subject2_column)]
            if extra_bind2_columns is not None:
                for key, value in extra_bind2_columns.items():
                    if key in subjects.subj2BindCol:
                        bind2.append(Bind(subjects.subj2BindCol[key], value))

        bind3 = None
        if subjects.year is not None:
            bind3 = [
                Bind(
                    subjects.yearBindCol[subject_year_bind_column_name],
                    bind_year_column,
                    UseDefaultCollate=True,
                )
            ]
            if extra_bind3_columns is not None:
                for key, value in extra_bind3_columns.items():
                    if key in subjects.yearBindCol:
                        bind3.append(Bind(subjects.yearBindCol[key], value))

        return bind1, bind2, bind3

    # ------------------------------------------------------------------
    # 內部轉換邏輯(私有方法,不對外暴露)
    # ------------------------------------------------------------------

    # 暫時用不到，2d沒有要轉成pd
    def _list2d_to_dataframe(
        self, result : list[list[str]], dtype_map: dict[str, str] | None = None
    ) -> pd.DataFrame:
        if result is None:
            return pd.DataFrame()

        rows = [list(row) for row in result]
        if not rows:
            return pd.DataFrame()

        header = rows[0]
        data_rows = rows[1:]

        df = pd.DataFrame(data_rows, columns=header)
        return self._apply_dtypes(df, dtype_map)

    def datatable_to_dataframe(self, dt, dtype_map: dict[str, str] | None = None) -> pd.DataFrame:
        if dt is None:
            return pd.DataFrame()

        columns = [col.ColumnName for col in dt.Columns]
        rows = [[row[col] for col in columns] for row in dt.Rows]

        df = pd.DataFrame(rows, columns=columns)

        # 對應原本 FormatDateTimeCol:偵測 datetime 欄位,轉成 yyyy-MM-dd 字串
        for i, col in enumerate(dt.Columns):
            if col.DataType.Name == "DateTime":  # .NET 型態名稱判斷
                df[columns[i]] = pd.to_datetime(df[columns[i]]).dt.strftime("%Y-%m-%d")

        return self._apply_dtypes(df, dtype_map)

    def _dataframe_to_datatable(self, df: pd.DataFrame, dtype_map: dict[str, str] | None = None):
        """
        把 pandas DataFrame 轉成 .NET DataTable,
        專門用在需要把資料傳回給 DLL function 的情境。
        """
        from System.Data import DataTable
        import clr
        import System

        dt = DataTable()

        # 建立欄位,依 dtype_map 指定型態,沒指定的話預設用 string
        for col in df.columns:
            if dtype_map and col in dtype_map:
                dotnet_type = self._python_dtype_to_dotnet_type(dtype_map[col])
            else:
                dotnet_type = System.String
            dt.Columns.Add(col, clr.GetClrType(dotnet_type))

        # 逐列填入資料
        for _, row in df.iterrows():
            nr = dt.NewRow()
            for col in df.columns:
                value = row[col]
                nr[col] = value if pd.notna(value) else System.DBNull.Value
            dt.Rows.Add(nr)
    
        return dt

    def _apply_dtypes(self, df: pd.DataFrame, dtype_map: dict[str, str] | None) -> pd.DataFrame:
        if not dtype_map:
            return df

        for col_name, dtype in dtype_map.items():
            if col_name not in df.columns:
                continue

            if dtype == "datetime64[ns]":
                df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
            else:
                df[col_name] = df[col_name].astype(dtype, errors="ignore")

        return df
