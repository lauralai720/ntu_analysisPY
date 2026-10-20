##namespace PRISAnalyzer.ESI.Class.ESIYear

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from rich import print as rprint
from abc import abstractmethod
import re

# PRIS dll 


# PRIS
import common.db_schema as db_schema
from common.year import *
from exceptions import PRISError
from database import Subject, Column, YearSubject, Table, Where, YTable, YJoinTable

class ESIYearStyle(Enum):
    Style1 = 0
    Style2 = auto()
    Style3 = auto()

@dataclass 
class ESIYear:
    Version: datetime
    Start: datetime
    End: datetime
    Style: ESIYearStyle = ESIYearStyle.Style1

    def __post_init__(self):
        if isinstance(self.Start, str):
            self.Start = self._parse_date(self.Start)
        if isinstance(self.End, str):
            self.End = self._parse_date(self.End)
        if isinstance(self.Version, str):
            self.Version = self._parse_date(self.Version)

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        date_part = date_str.split(" ")[0]  # 用空格切開,取第一段(日期部分)
        return datetime.strptime(date_part, "%Y/%m/%d")

    def __str__(self) -> str:
        return self.to_str(self.Style)

    def to_str(self, time_style: ESIYearStyle) -> str :
        if (time_style == ESIYearStyle.Style1):
            return f"{self.Start.strftime('%Y')}-{self.End.strftime('%Y')}"
        elif (time_style == ESIYearStyle.Style2):
            return f"{self.Start.strftime('%Y/%m/%d')}-{self.End.strftime('%Y/%m/%d')}"
        else:
            return f"{self.Start.strftime('%Y')}-{self.End.strftime('%Y')}上"

    ## public string ToShortString()
    def get_verion_str(self)->str:
        return self.Version.strftime('%Y-%m-%d')


class YearSelector:
    def __init__(self):
        self.UserColumnName:str = ""

    @abstractmethod
    def get_subject(self) -> tuple["Subject", dict[str, "Column"]]:
        pass


class ESIYearSelector(YearSelector):
    def __init__(self):
        self.selected_main: ESIYear = None
        self.selected_comp: ESIYear = None
        self.year_list : list[ESIYear] = self._fetch_year_list()

    def _fetch_year_list(self) -> list[ESIYear]:
        from dal_provider import get_dal
        dal = get_dal()
        strCmd = (
            f"SELECT {db_schema.schema.ESIUpdateTimeColumnName}, {db_schema.schema.DataRangeStartColumnName}, {db_schema.schema.DataRangeEndColumnName} "
            f"FROM {db_schema.schema.ESIRawDataVersionTableName} WHERE {db_schema.schema.ESIUpdateTimeColumnName} IN " 
            f"(SELECT DISTINCT {db_schema.schema.ESIUpdateTimeColumnName} FROM {db_schema.schema.ESIRawDataForInstitutionTableName} "
            f"UNION SELECT DISTINCT {db_schema.schema.ESIUpdateTimeColumnName} FROM {db_schema.schema.ESIRawDataForResearchFieldTableName}) " 
            f"ORDER BY {db_schema.schema.ESIUpdateTimeColumnName} DESC"
        )

        year_rows = dal.query_2d_raw(strCmd)

        return [ESIYear(row[0], row[1], row[2]) for row in year_rows]
    
    
    # 從外部帶入
    # main_ver : yyyy-MM-dd
    def set_versions(self, main_ver :str, comp_ver:str):
        main_year = next((x for x in self.year_list if x.get_verion_str() == main_ver), None)
        if main_year is None:
            rprint("[red]Error : 沒有主要版本的年份資料[/red]")
            return
        comp_year = next((x for x in self.year_list if x.get_verion_str() == comp_ver), None)
        if comp_year is None:
            rprint("[red]Error : 沒有比較版本的年份資料[/red]")
            return

        self.selected_main = main_year
        self.selected_comp = comp_year

    def get_selected(self) -> list[ESIYear] : 
        return [self.selected_main, self.selected_comp]

    def get_subject(self) -> tuple["Subject", dict[str, "Column"], str]:
            from dal_provider import get_dal
            dal = get_dal()
            tbl = dal.create_table(db_schema.schema.MainTableName)
            col_update_time = tbl.RetrieveColumn(db_schema.schema.ESIUpdateTimeColumnName)
            subj = dal.create_subject(tbl,col_update_time)
            subj.Initialize()
    
            years = [self.selected_main, self.selected_comp]
    
            for t in years:
                # 原本是subj.Add(v.Version.ToString("yyyy-MM-dd"));
                # 看起來跟 get_verion_str 一樣所以擅自改了
                subj.Add(t.get_verion_str())
    
            bind_columns = {db_schema.schema.ESIUpdateTimeColumnName : col_update_time}
    
            return subj, bind_columns, "版本"

# 裡面create YearSubject
class PaperYearSubject():
    def __init__(self, table:"Table", val_col : "Column", need_year_func_wrap: bool = True, col_name : str= ""):
        from dal_provider import get_dal
        dal = get_dal()
        y_table = dal.create_year_table(table, False)
        self._year_subject : "YearSubject" = dal.create_year_subject(y_table, val_col, need_year_func_wrap)
        self.subj.table.RetrieveColumn(db_schema.schema.PublishDateColumnName)
        self.col_name = col_name
        self.supported_year_type = SupportYearType.WholeYear | SupportYearType.HalfYear
        
    @property
    def subj(self) -> "YearSubject" :
        return self._year_subject

    def add(self, subj_val:str, where_list:list["Where"] = None):
        if not self.subj.initialized:
            raise PRISError("YearSubject 尚未初始化, 請先執行 YearSubject.Initial() ")

        self.subj.column.set_name(self.subj.use_column_name)

        period = re.compile(r"\d{4}-\d{4}$")
        single = re.compile(r"\d{4}$")
        periodHalf = re.compile(r"\d{4}H[1-2]-\d{4}H[1-2]$")
        singleHalf = re.compile(r"\d{4}H[1-2]$")


        firstHalfList_Month = ["1", "2", "3", "4", "5", "6"]
        secondHalfList_Month = ["7", "8", "9", "10", "11", "12"]
        firstAndSecondHalfList_Month = firstHalfList_Month + secondHalfList_Month

        # where_arr = None
        # if where_list is not None:
        #     where_arr = dal.to_csharp_array(where_list)

        if period.match(subj_val):
            years = subj_val.split('-')
            from_year = int(years[0]) -1
            to_year = int(years[1]) +1
            if isinstance(self.subj.table, (YTable, YJoinTable)):
                self.subj.table.insert_temp_table(self.subj.column, val=from_year, less_val=to_year, label=subj_val, wheres=where_list)

        elif single.match(subj_val):
            year = int(subj_val)
            if isinstance(self.subj.table, (YTable, YJoinTable)):
                self.subj.table.insert_temp_table(self.subj.column, val=year, label=subj_val, wheres=where_list)
        else:
            # [Bug fix] 原本 raise("字串") → TypeError: exceptions must derive from BaseException
            raise PRISError(f"目前沒有其他格式的年份要處理: {subj_val}")

        self.subj.subj_vals.append(subj_val)
        self.subj.column.set_name("Year")

class WOSYearSelector(YearSelector):
    def __init__(self):
        self.need_year_func_wrap : bool = False # 值來源至PresidentReport
        self.year_list : list[str] = None

    def get_subject(self) -> tuple["Subject", dict[str, "Column"], str]:
        if not self.year_list:
            return (None, None, None)

        from dal_provider import get_dal
        dal = get_dal()

        main_table = dal.create_table(db_schema.schema.MainTableName)
        time_col = main_table.RetrieveColumn(db_schema.schema.TimeColumnName)
        bind_col = main_table.RetrieveColumn(db_schema.schema.MainBindColumnName)

        year_subject = PaperYearSubject(main_table, time_col, self.need_year_func_wrap, db_schema.schema.TimeColumnName)
        # year_subject.subj.AllowNonWholeYear = False #目前沒用到，先註解
        year_subject.subj.Initialize()

        for year in self.year_list:
            year_subject.add(year)

        bind_columns = {
            db_schema.schema.MainBindColumnName : bind_col
        }

        return (year_subject.subj, bind_columns, "年份")

    def get_years(self) -> list[Year]:
        year_list : list[Year] = []
        for y in self.year_list:
            year_obj = Year(y)
            year_list.append(year_obj)
        if not year_list:
            year_list.append(None)

        return year_list

