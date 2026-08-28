##namespace PRISAnalyzer.ESI.Class.ESIYear

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from rich import print as rprint

# PRIS dll 


# PRIS
import db_schema

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
        self.year_list: list[ESIYear] = None
        self.selected_main: ESIYear = None
        self.selected_comp: ESIYear = None
        self.year_list = self._fetch_year_list()

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

    def get_selected(self) -> list[ESIYear] : 
        return [self.selected_main, self.selected_comp]

    def get_subject(self, only_fetch_selected : bool = False) -> tuple["Subject", dict[str, "Column"]]:
        if only_fetch_selected:
            return None, None
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

        return subj, bind_columns

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
