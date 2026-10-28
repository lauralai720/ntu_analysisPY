#python 需要套件(繼承、自訂型態等等)
from abc import ABC
from dataclasses import dataclass,field
from typing import Callable, Optional, TypeAlias
from functools import cached_property
import pandas as pd

# PRIS 相關套件
import common.db_schema as db_schema
from components.subjects import Subjects
from dal_provider import get_dal
from components.year_selector import ESIYear
import common.util as Util
from . import data_analysis as DataAnalysis
from database import *
from exceptions import PRISError

dal = get_dal()

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
                    use_default_collate=True,
                )
            ]
            if extra_bind3_columns is not None:
                for key, value in extra_bind3_columns.items():
                    if key in subjects.yearBindCol:
                        bind3.append(Bind(subjects.yearBindCol[key], value))

        return bind1, bind2, bind3

# 主區域
# ================================================================
# Metrics
@dataclass
class ReplaceSubject:
    subject : Optional["Subject"] = None
    bind_column : Optional["Column"] = None

@dataclass
class ComputeObject:
    main_column : Optional["Column"] = None
    bind_column : Optional["Column"] = None
    subject1_bind_col_name : str = ""
    subject2_bind_col_name : str = ""
    subject_year_bind_col_name : str = ""
    join_table : Optional["JoinTable"] = None
    table : Optional["Table"] = None
    main_table : Optional["Table"] = None
    distinct : bool = False
    subjects : Optional[Subjects] = None

    where_clauses: list["Where"] = field(default_factory=list)
    replace_bind_col_of_subject1 : Optional["Column"] = None
    replace_bind_col_of_subject2 : Optional["Column"] = None
    replace_bind_col_of_year : Optional["Column"] = None
    replace_subject1 : Optional[ReplaceSubject] = None
    replace_subject2 : Optional[ReplaceSubject] = None
    replace_subject3 : Optional[ReplaceSubject] = None
    extra_bind1_columns : Optional[dict[str, "Column"]] = None
    extra_bind2_columns : Optional[dict[str, "Column"]] = None
    extra_bind3_columns : Optional[dict[str, "Column"]] = None
    bind_subject1 : bool = False
    bind_subject2 : bool = False
    bind_year : bool = False
    _keep_col :  Optional[list["Column"]] = None


    @property
    def compute_table(self) :
        if self.join_table is None:
            return self.table
        else:
            return self.join_table


    @property
    def query(self) -> "Query":
        bind_subj1_col = self.main_column if self.replace_bind_col_of_subject1 is None else self.replace_bind_col_of_subject1
        bind_subj2_col = self.main_column if self.replace_bind_col_of_subject2 is None else self.replace_bind_col_of_subject2
        bind_year_col = self.main_column if self.replace_bind_col_of_year is None else self.replace_bind_col_of_year

        bind1, bind2, bind3 = get_binds(
            bind_subject1_column= bind_subj1_col, 
            bind_subject2_column=bind_subj2_col,
            bind_year_column=bind_year_col,
            subjects=self.subjects,
            subject1_bind_column_name=self.subject1_bind_col_name if self.subject1_bind_col_name else db_schema.schema.MainBindColumnName,
            subject2_bind_column_name=self.subject2_bind_col_name if self.subject2_bind_col_name else db_schema.schema.MainBindColumnName,
            subject_year_bind_column_name=self.subject_year_bind_col_name if self.subject_year_bind_col_name else db_schema.schema.MainBindColumnName,
            extra_bind1_columns= self.extra_bind1_columns,
            extra_bind2_columns= self.extra_bind2_columns,
            extra_bind3_columns= self.extra_bind3_columns,
        )

        #q = dal.create_query(self.compute_table)
        q = Query(self.compute_table)

        if bind1 is not None and self.bind_subject1:
            q.set_subject1(self.subjects.subject1, bind1)
        if bind2 is not None and self.bind_subject2:
            q.set_subject2(self.subjects.subject2, bind2)
        if bind3 is not None and self.bind_year:
            q.set_subject3(self.subjects.year, bind3)

        if self.replace_subject1 is not None and self.bind_subject1:
            q.set_subject1(self.replace_subject1.subject, Bind(self.replace_subject1.bind_column, bind_subj1_col))

        if self.replace_subject2 is not None and self.bind_subject2:
            q.set_subject2(self.replace_subject2.subject, Bind(self.replace_subject2.bind_column, bind_subj1_col))

        if self.replace_subject3 is not None and self.bind_year:
            q.set_subject3(self.replace_subject3.subject, Bind(self.replace_subject3.bind_column, bind_subj1_col, use_default_collate=True))

        return q

    @property
    def keep_column(self):
        """對應 getter"""
        if self._keep_col is None:
            self._keep_col = [self.main_column]

        return self._keep_col

    @keep_column.setter
    def keep_column(self, value):
        """對應 setter"""
        self._keep_col = value


    # 改動BindSubjects，用 bind_subjects(true/false)
    def bind_subjects(self, val : bool) -> bool :
        self.bind_subject1 = val
        self.bind_subject2 = val
        self.bind_year = val

    ## 原 : public DataTable Count(bool RemoveSubjColumn = false, Column[] OrderBy = null, string CountFunc = "COUNT")
    def to_count(self, remove_subj_col : bool = False, orderby : list["Column"] = None, count_func = "COUNT"):
        return self.query.count(
            self.main_column, 
            distinct= self.distinct, 
            keep_cols=self.keep_column, 
            order_by= orderby, 
            wheres= self.where_clauses, 
            remove_subj_col= remove_subj_col, 
            count_func= count_func,
        )
    ## 原 : public DataTable List(bool RemoveSubjColumn = false, Column[] OrderBy = null)
    def to_list(self, remove_subj_col : bool = False, orderby : list["Column"] = None):
        keep = self.keep_column
        return self.query.select(
            distinct= self.distinct, 
            keep_cols= keep, 
            order_by= orderby, 
            remove_subj_col= remove_subj_col,
            wheres= self.where_clauses
        )
    
    def add_keep_col(self, columns, idx: int = None):
        if isinstance(columns, list):
            #go list function
            self.keep_column.extend(columns)
        elif idx is not None:
            self.keep_column.insert(idx, columns)
        else:
            self.keep_column.extend([columns])

    def add_where_clause(self, clauses):
        inset_list = clauses if isinstance(clauses, list) else [clauses]

        if self.where_clauses is None:
            self.where_clauses = []

        self.where_clauses.extend(inset_list)

    def get_joined_right_table(self) -> Table :
        return self.join_table.right

    def get_joined_left_table(self)-> Table:
        return self.join_table.left
        
    
@dataclass
class Metrics(ABC):
    subjects : Optional[Subjects] = None
    bind_subject1 : bool = True
    bind_subject2 : bool = True
    bind_year : bool = True

    get_where_clauses: Callable[["Table"], list["Where"]] = None

    def main_paper_count(self) -> pd.DataFrame:
        res_df = self.get_count(db_schema.schema.MainBindColumnName)
        return res_df
        #return dal.datatable_to_dataframe(res_dt)

    def get_main_table_and_bind_col(self) -> tuple["Table", "Column"]:
        #dal = get_dal()
        main_table = dal.create_table(db_schema.schema.MainTableName)
        bind_col = None
        if db_schema.schema.MainBindColumnName is not None:
            bind_col = main_table.RetrieveColumn(db_schema.schema.MainBindColumnName)

        return main_table, bind_col

    def get_compute_object(self, main_col_name:str, dist: bool = True) -> ComputeObject:
        main_t, bind_col = self.get_main_table_and_bind_col()
        main_col = main_t.RetrieveColumn(main_col_name)
        where_list = self.get_where_clauses(main_t)

        return ComputeObject(
            subjects=self.subjects,
            main_table=main_t,
            table=main_t,
            bind_column=bind_col,
            main_column=main_col,
            where_clauses=where_list,
            distinct=dist,
            bind_subject1=self.bind_subject1,
            bind_subject2=self.bind_subject2,
            bind_year=self.bind_year,
        )

    def get_compute_object_with_join_table(self, 
                                           main_col_name:str, 
                                           join_table_name:str, 
                                           join_column_name:str, 
                                           join_main_table_column_name:str, 
                                           main_column_concat : list[str] | None = None, 
                                           main_column_in_main_table : bool= False, 
                                           join_type = dal.JOINTYPE.InnerJoin, 
                                           dist:bool = True, 
                                           func :str = ""
    ):
        (main_table, bind_column) = self.get_main_table_and_bind_col()
        join_main_col = main_table.RetrieveColumn(join_main_table_column_name)

        table2 = Table(join_table_name)
        join_col = table2.RetrieveColumn(join_column_name)

        main_col_table = None
        main_col = None
        if main_column_in_main_table:
            main_col_table = main_table
        else:
            main_col_table = table2

        if main_column_concat:
            main_col = main_col_table.RetrieveColumn(main_col_name, concat=main_column_concat)
        else:
            main_col = main_col_table.RetrieveColumn(main_col_name, func=func)
        

        on = dal.create_join_on(left=join_main_col, right=join_col)
        join_table = dal.create_join_table(left=main_table, right=table2, join_type=join_type, on=on, collate="DATABASE_DEFAULT")
        
        return ComputeObject(
            subjects = self.subjects,
            main_table= main_table,
            join_table= join_table,
            bind_column= bind_column,
            main_column= main_col,
            where_clauses= self.get_where_clauses(main_table),             
            distinct= dist,
            bind_subject1= self.bind_subject1,
            bind_subject2= self.bind_subject2,
            bind_year= self.bind_year
        )
        

    def get_list(self, main_col_name: str, dist: bool = True) -> pd.DataFrame:
        return self.get_compute_object(main_col_name, dist).to_list()

    def get_count(self, main_col_name:str, dist: bool = True, count_func="COUNT") -> pd.DataFrame:
        return self.get_compute_object(main_col_name, dist).to_count(count_func = count_func)
    
    
# ESIMetrics
@dataclass
class RankItem:
    number:float
    rank:int

@dataclass
class OrgAttrInfoItem:
    country:str
    continent:str


VERSION_FIELD_RANK: TypeAlias = dict[str, dict[str, list[RankItem]]]
COLUMN_VERSION_FIELD_RANK: TypeAlias = dict[str, dict[str, dict[str, list[RankItem]]]]


@dataclass
class ESIMetrics(Metrics):
    INSTITUTION_SUBJECT_NAME : str = "Institution"
    FIELD_SUBJECT_NAME : str = "Field"
    DECIMAL_PLACES: int = 2
    asia_pacific : list[str] =field(default_factory=lambda: ["Asia", "Oceania"])
    _world_rank : Optional[COLUMN_VERSION_FIELD_RANK] = field(default_factory=dict)
    _asia_pacific_rank: Optional[COLUMN_VERSION_FIELD_RANK] = field(default_factory=dict)

    @property
    def select_versions(self) -> list[ESIYear]:
        return self.subjects.selectedYear

    @property
    def avg_cited_func(self) -> str:
        return f"ROUND(CAST(SUM({db_schema.schema.CiteColumnName}) AS float)/CAST(SUM({db_schema.schema.PaperCountColumnName}) AS float), {self.DECIMAL_PLACES})"

    @property
    def is_sub_field(self) -> bool :
        return self.subjects.ShownByESI_ID

    @property
    def subj2_selected_fields(self) -> list[str] : 
        return self.subjects.selectedVal2
    ### E1
    @cached_property
    def paper_count(self) -> pd.DataFrame:
        res = DataAnalysis.a02_sumup_calculate(df = ESIMetrics.format_datetime_col(self.get_list(db_schema.schema.PaperCountColumnName, dist=False)))
        return res
    
    @cached_property
    def world_paper_count_rank(self) -> pd.DataFrame:
        return self.world_rank(self.paper_count, self.get_world_rank_of_selected_version(db_schema.schema.PaperCountColumnName)) 
    @cached_property
    def asia_pacific_paper_count_rank(self) -> pd.DataFrame:
        return self.asia_pacific_rank(self.paper_count, db_schema.schema.PaperCountColumnName)
    ### E2
    @cached_property
    def cited(self) -> pd.DataFrame:
        res = DataAnalysis.a02_sumup_calculate(df = ESIMetrics.format_datetime_col(self.get_list(db_schema.schema.CiteColumnName, dist=False)))
        return res
    @cached_property
    def world_cited_rank(self) -> pd.DataFrame:
        return self.world_rank(self.cited, self.get_world_rank_of_selected_version(db_schema.schema.CiteColumnName)) 
    @cached_property
    def asia_pacific_cited_rank(self) -> pd.DataFrame:
        return self.asia_pacific_rank(self.cited, db_schema.schema.CiteColumnName)
    ### E3
    @cached_property
    def avg_cited(self) -> pd.DataFrame:
        return self.div_data_tables(self.cited, self.paper_count)
    ### E4
    @cached_property
    def hici(self) -> pd.DataFrame: 
        res = DataAnalysis.a02_sumup_calculate(df = ESIMetrics.format_datetime_col(self.get_list(db_schema.schema.HighlyCitedPaperCountColumnName, dist=False)))
        return res
    ### E5
    @cached_property
    def hot(self) -> pd.DataFrame:
        res = DataAnalysis.a02_sumup_calculate(df = ESIMetrics.format_datetime_col(self.get_list(db_schema.schema.HotPaperColumnName, dist=False)))
        return res

    @cached_property
    def org_attr_info(self) -> dict[str, OrgAttrInfoItem]:
        is_ac = True # self.subjects.selectedVal1.IsAC is True
        query_org_col = db_schema.schema.OrgSerialColumnName if is_ac else db_schema.schema.EsiACColumnName
        cmd_str = (
            f"SELECT DISTINCT Info.{query_org_col}, Info.{db_schema.schema.CountrySerialColumnName}, Info.{db_schema.schema.ContinentColumnName} FROM {db_schema.schema.EsiAcAttrInfoTableName} Info INNER JOIN "
            f"(SELECT MAX({db_schema.schema.ESIUpdateTimeColumnName}) AS {db_schema.schema.ESIUpdateTimeColumnName}, MAX({db_schema.schema.TimeStartColumnName}) AS {db_schema.schema.TimeStartColumnName}, {query_org_col} FROM {db_schema.schema.EsiAcAttrInfoTableName} WHERE {db_schema.schema.TimeEndColumnName} IS NULL GROUP BY {query_org_col}) Latest "
            f"ON Info.{query_org_col} = Latest.{query_org_col} AND Info.{db_schema.schema.TimeStartColumnName} = Latest.{db_schema.schema.TimeStartColumnName}"
        )
        if is_ac:
            cmd_str += f" WHERE Info.{db_schema.schema.OrgSerialColumnName} != ''"

        qret = dal.query_2d_raw(cmd_str)
        qert_arr = []
        for x in qret:
            qert_arr.append({ "Org" : x[0], "Country" : x[1], "Continent" : x[2]})

        res = {}

        for item in qert_arr:
            res[item["Org"]] = OrgAttrInfoItem(country=item["Country"],continent=item["Continent"])

        return res

    def get_compute_object(self, main_col_name, dist = True) -> ComputeObject:
        compute_obj = super().get_compute_object(main_col_name, dist)
        if self.subjects.subject1 is not None:
            subj1_bind_col_name = next(iter(self.subjects.subj1BindCol), None)
            compute_obj.subject1_bind_col_name = subj1_bind_col_name
            compute_obj.replace_bind_col_of_subject1 = compute_obj.main_table.RetrieveColumn(subj1_bind_col_name)

        if self.subjects.subject2 is not None:
            subj2_bind_col_name = next(iter(self.subjects.subj2BindCol), None)
            compute_obj.subject2_bind_col_name = subj2_bind_col_name
            compute_obj.replace_bind_col_of_subject2 = compute_obj.main_table.RetrieveColumn(subj2_bind_col_name)

        if self.subjects.year is not None:
            year_bind_col_name = next(iter(self.subjects.yearBindCol), None)
            compute_obj.subject_year_bind_col_name = year_bind_col_name
            compute_obj.replace_bind_col_of_year = compute_obj.main_table.RetrieveColumn(year_bind_col_name)

        return compute_obj

    def world_rank(self, df: pd.DataFrame, version_field_rank: VERSION_FIELD_RANK) -> pd.DataFrame:
        """對應 C# 的 WorldRank(DataTable dt, VERSION_FIELD_RANK version_field_rank)"""
        df_ret = df.copy()

        val_col_idx = len(df.columns) - 1
        ver_col_idx = val_col_idx - 1

        def compute_rank(row) -> str:
            version = str(row.iloc[ver_col_idx])
            num = float(row.iloc[val_col_idx])

            if self.subjects.subject2 is None:
                ranking_list = version_field_rank[version][""]
            else:
                field = int(row.iloc[1])
                ranking_list = version_field_rank[version][field]

            rank = ESIMetrics.binary_search_find_rank(ranking_list, num)
            return str(rank)

        df_ret[df_ret.columns[val_col_idx]] = df_ret[df_ret.columns[val_col_idx]].astype(str)  # 先把欄位轉成字串型態
        df_ret.iloc[:, val_col_idx] = df_ret.apply(compute_rank, axis=1)
        return df_ret

    def asia_pacific_rank(self, df: pd.DataFrame, col_name : str, func:str=None, versions:list[ESIYear]=None)-> pd.DataFrame:
        return self.region_rank(df, col_name, self.get_asia_pacific_rank, "continent", func, versions, qualified=self.asia_pacific)

    def region_rank(self, 
                    df: pd.DataFrame, 
                    col_name:str, 
                    caller_get_rank:Callable[[str, str, str, list[str]], VERSION_FIELD_RANK],
                    prop:str,
                    func:str = None,
                    versions: list[ESIYear] = None,
                    qualified: list[str] = None
                ) ->  pd.DataFrame:
        original_columns = list(df.columns[:-1])
        new_columns = original_columns + ["rank"]

        ret_rows = []

        val_col_idx = len(df.columns) - 1
        ver_col_idx = val_col_idx - 1
        org_col_idx = 0

        for _, row in df.iterrows():
            org = str(row.iloc[org_col_idx])
            ver = str(row.iloc[ver_col_idx])
            val = float(row.iloc[val_col_idx])

            row_val = "N/A"
            if org in self.org_attr_info:
                org_info = self.org_attr_info[org]
                region = str(getattr(org_info, prop))
                
                if qualified is not None and region not in qualified:
                    row_val = "--"
                else:
                    if self.subjects.subject2 is None :
                        ranking_list = caller_get_rank(col_name=col_name, _=region, func=func, versions=versions)[ver][""]
                    else:
                        field = row.iloc[1]
                        ranking_list = caller_get_rank(col_name=col_name, _=region, func=func, versions=versions)[ver][field]

                    rank = ESIMetrics.binary_search_find_rank(rank_list=ranking_list, goal_num=val)
                    row_val = str(rank)

            new_row = list(row.iloc[:val_col_idx]) + [row_val]
            ret_rows.append(new_row)

        res = pd.DataFrame(ret_rows, columns=new_columns)
        return res


    def get_asia_pacific_rank(self, col_name:str, _:str, func:str=None,versions:list[ESIYear]= None)-> VERSION_FIELD_RANK:
        if func is None:
            func = f"SUM({col_name})"

        if col_name not in self._asia_pacific_rank:
            self._asia_pacific_rank[col_name] = self.get_rank(func=func, region_col_name=db_schema.schema.ContinentColumnName, regions=self.asia_pacific, versions=versions)
        else:
            if versions is None:
                versions = self.select_versions
            new_vers = [x for x in versions if x.get_verion_str() not in self._asia_pacific_rank[col_name]]
            if len(new_vers) > 0 :
                new_ranks = self.get_rank(func=func, region_col_name=db_schema.schema.ContinentColumnName, regions=self.asia_pacific, versions=new_vers)
                ## 原語法 asiaPacificRank[colName] = asiaPacificRank[colName].Concat(newRanks).ToLookup(x => x.Key, x => x.Value).ToDictionary(x => x.Key, x => x.First());
                ## 舊資料為主，新增新key的資料
                ## python寫法 {**a, **b}，如果 a 跟 b 有重複 key，後面的 b 會覆蓋前面的 a
                self._asia_pacific_rank[col_name] = {**new_ranks, **self._asia_pacific_rank[col_name]}

        return self._asia_pacific_rank[col_name]


    def get_rank(self,func:str, region_col_name:str, regions:list[str], versions: list[ESIYear] = None) -> VERSION_FIELD_RANK:
        if versions is None:
            versions = self.select_versions

        vers_str = ESIMetrics.get_vers_str(versions=versions)
        region_str = ""
        for i in range(len(regions)):
            if i == 0:
                region_str += f"(AcInfo.{region_col_name} = '{regions[i]}'"
            else:
                region_str += f" OR AcInfo.{region_col_name} = '{regions[i]}'"
            if i == len(regions)-1:
                region_str += ")"

        shown_field_col = db_schema.schema.ESIIDColumnName if self.is_sub_field else db_schema.schema.FIDColumnName
        select_field_name = "''" if self.subjects.subject2 is None else ", " + shown_field_col

        cmd_str = (
            f"SELECT {db_schema.schema.ESIUpdateTimeColumnName}{select_field_name}, {func}, "
            f"RANK() OVER(PARTITION BY {db_schema.schema.ESIUpdateTimeColumnName}{select_field_name} ORDER BY {func} DESC) AS RANK FROM {db_schema.schema.ESIRawDataForInstitutionTableName} Inst "
        )

        if self.subjects.subject2 is not None:
            cmd_str += f"INNER JOIN {db_schema.schema.PaperFieldESITableName} ESIField ON Inst.{db_schema.schema.ESICategoryColumnName} = ESIField.{db_schema.schema.ESIIDColumnName} "

        cmd_str += f"WHERE EXISTS(SELECT * FROM {db_schema.schema.EsiAcAttrInfoTableName} AcInfo WHERE Inst.{db_schema.schema.InstitutionColumnName} = AcInfo.{db_schema.schema.EsiACColumnName} AND {region_str} AND {db_schema.schema.TimeEndColumnName} IS NULL) AND ({vers_str}) "

        if self.subjects.subject2 is not None:
            condintions = "','".join([str(f) for f in self.subj2_selected_fields])
            cmd_str += f"AND {db_schema.schema.FIDColumnName} IN ('{condintions}')"

        cmd_str += f" GROUP BY {db_schema.schema.ESIUpdateTimeColumnName}, {db_schema.schema.InstitutionColumnName}{select_field_name}"

        query_res = dal.query_2d_raw(cmd_str)

        ret: VERSION_FIELD_RANK = {}
        
        for x in query_res:
            version = ESIMetrics.format_date_str(x[0])
            field = x[1]
            number = float(x[2])
            rank = int(x[3])

            if version not in ret:
                ret[version] = {}
            if field not in ret[version]:
                ret[version][field] = []

            ret[version][field].append(RankItem(number=number, rank=rank))

        return ret

    def get_world_rank_of_selected_version(self, col_name: str, func_str : str = None)->VERSION_FIELD_RANK:
        if func_str == None:
            func_str = f"SUM({col_name})"
        if col_name not in self._world_rank:
            self._world_rank[col_name] = self.get_world_rank(func_str=func_str,versions=self.select_versions)

        return self._world_rank[col_name]

    # private VERSION_FIELD_RANK getWorldRank
    def get_world_rank(self, func_str : str, versions: list[ESIYear]):
        shown_field_col = db_schema.schema.ESIIDColumnName if self.is_sub_field else db_schema.schema.FIDColumnName
        select_field_name = "''" if self.subjects.subject2 is None else ", " + shown_field_col
        cmd_str = (
            f"SELECT {db_schema.schema.ESIUpdateTimeColumnName}, {db_schema.schema.InstitutionColumnName}{select_field_name}, {func_str} AS Count, "
            f"RANK() OVER(PARTITION BY {db_schema.schema.ESIUpdateTimeColumnName}{select_field_name} ORDER BY {func_str} DESC) AS Rank "
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} Inst "
        )
        if self.subjects.subject2 is not None:
            cmd_str += f"INNER JOIN {db_schema.schema.PaperFieldESITableName} ESIField ON Inst.{db_schema.schema.ESICategoryColumnName} = ESIField.{db_schema.schema.ESIIDColumnName} "

        cmd_str += f"WHERE 1 = 1"

        if self.subjects.subject2 is not None:
            condintions = "', '".join([str(f) for f in self.subj2_selected_fields])
            cmd_str += f" AND {db_schema.schema.FIDColumnName} IN ('{condintions}')"

        if len(versions) > 0:
            cmd_str += " AND ("

            for i in range(len(versions)):
                if i == 0:
                    cmd_str += f"{db_schema.schema.ESIUpdateTimeColumnName} = '{versions[i].get_verion_str()}'"
                else:
                    cmd_str += f" OR {db_schema.schema.ESIUpdateTimeColumnName} = '{versions[i].get_verion_str()}'"
            
            cmd_str += ")"

        cmd_str += f" GROUP BY {db_schema.schema.ESIUpdateTimeColumnName}, {db_schema.schema.InstitutionColumnName}{select_field_name}"

        query_res = dal.query_2d_raw(cmd_str)

        # 第二 + 三階段:依 version 分組,組內再依 field 分組
        ret: VERSION_FIELD_RANK = {}

        for x in query_res:
            version = ESIMetrics.format_date_str(x[0])
            field = x[2]
            number = float(x[3])
            rank = int(x[4])

            if version not in ret:
                ret[version] = {}
            if field not in ret[version]:
                ret[version][field] = []

            ret[version][field].append(RankItem(number=number, rank=rank))

        return ret

    def div_data_tables(self, df1 : pd.DataFrame, df2: pd.DataFrame, use_percent_age: bool = False)-> pd.DataFrame:
        subj_num = len(df1.columns) - 1
        if subj_num <= 0:
            raise PRISError(f"合併欄位數量{subj_num}不合法")
        if subj_num > 3:
            subj_num = 3 # 原本的寫法只會替換前1~3個欄位

        df_merge = Util.join_diff_dataframes(df1,df2,subj_num)

        res = DataAnalysis.a08_cntavg_calculate(df_merge, 2 + self.DECIMAL_PLACES if use_percent_age else self.DECIMAL_PLACES)
        res = res.drop(columns=["Column1","Column2"])

        if use_percent_age:
            # [Bug fix] iterrows() 給的是「複本」,對 row 賦值不會改到 res,這段原本完全沒有作用
            last = res.columns[-1]
            res[last] = res[last].map(lambda v: str(float(v) * 100) + "%")

        return res

    ### ==================
    ### Static method
    ### ==================
    @staticmethod
    def format_datetime_col(df : pd.DataFrame) -> pd.DataFrame:
        df_new = df.copy(deep=True)
        datetime_cols = df_new.select_dtypes(include=['datetime64', 'datetime']).columns
        for col in datetime_cols:
            df_new[col] = df_new[col].dt.strftime('%Y-%m-%d')

        return df_new
    
    @staticmethod
    def format_date_str(date: str) -> str:
        return date.strftime("%Y-%m-%d")

    @staticmethod
    def get_vers_str(versions : list[ESIYear]) -> str :
        vers_str =""
        for ver in versions:
            if vers_str != "":
                vers_str += " OR "
            vers_str += f"{db_schema.schema.ESIUpdateTimeColumnName} = '{ver.get_verion_str()}'"

        return vers_str
    
    @staticmethod
    def binary_search_find_rank(rank_list: list[RankItem], goal_num : float):
        head = 0
        tail = len(rank_list) - 1
        while head < tail:
            mid = (head + tail) // 2
            if  rank_list[mid].number == goal_num:
                return rank_list[mid].rank
            elif rank_list[mid].number < goal_num:
                tail = mid- 1
                continue
            else:
                head = mid+1
                continue

        if not rank_list:                       # [Bug fix] 空清單原本是 IndexError
            raise PRISError("排名清單為空,無法計算排名")
        if rank_list[head].number <= goal_num:
            return rank_list[head].rank
        else:
            return rank_list[head].rank+1

@dataclass
class PaperMetrics(Metrics):
    @cached_property
    def cited(self) -> pd.DataFrame:
        compute_object = self.get_compute_object_with_join_table(db_schema.schema.MainBindColumnName, db_schema.schema.CitationsCountTableName, db_schema.schema.MainBindColumnName, db_schema.schema.MainBindColumnName, dist=True)
        col_cited_count = compute_object.get_joined_right_table().RetrieveColumn(db_schema.schema.CitedCountColumnName)
        compute_object.add_keep_col(col_cited_count)
        df_ret = compute_object.to_list()
        df_ret = df_ret.drop(df_ret.columns[-2], axis=1)

        return DataAnalysis.a02_sumup_calculate(df=df_ret)

from common.year import Year

@dataclass 
class GrowthRate(Metrics):
    _pre_year_list: list[Year] | None = None
    ori_year_list: list[str] | None = None

    @property
    def pre_year_list(self) -> list[Year]:
        if self._pre_year_list is None:
            self._pre_year_list = self._get_pre_year_list()
        return self._pre_year_list

    def _already_in_list(self, year: Year, year_list: list[Year]) -> bool:
        pre_y = year.add(-1)
        return any(x == pre_y for x in year_list)

    def _get_pre_year_list(self) -> list["Year"]:
        pre_year_list: list["Year"] = []

        for y in self.subjects.year_list:
            if self._already_in_list(y, self.subjects.year_list):
                continue
            if self._already_in_list(y, pre_year_list):
                continue

            pre_year_list.append(y.add(-1))

        return pre_year_list

    def calculate_growth_rate(self, input_data, use_percent_age: bool = True, na_val_notation=None) -> pd.DataFrame:
        if self.subjects.subject1 is None:
            y_idx = 0
        elif self.subjects.subject2 is None:
            y_idx = 1
        else:
            y_idx = 2

        if self.ori_year_list is None:
            self.ori_year_list = list(dict.fromkeys(str(x) for x in self.subjects.YearList))

        def pre_y_func(x: str) -> str:
            return str(Year(x).add(-1))

        df_ret = DataAnalysis.growth_rate_calculate(
            input_data, y_idx, self.ori_year_list, pre_y_func, use_percent_age, na_val_notation
        )
        return df_ret

    def add_pre_year_list_to_year_subject(self):
        self.ori_year_list = list(dict.fromkeys(str(x) for x in self.subjects.YearList))

        for y in self.pre_year_list:
            self.subjects.year.append(str(y))
            self.subjects.YearList.append(y)

@dataclass
class PaperList(Metrics):
    def cited_count(self,remove_subj_column : bool = False, keep_column : "Column" = None) -> pd.DataFrame:
        compute_object = self.get_compute_object_with_join_table(
            db_schema.schema.MainBindColumnName, 
            db_schema.schema.CitationsCountTableName, 
            db_schema.schema.MainBindColumnName, 
            db_schema.schema.MainBindColumnName
        )

        cited_count_col = compute_object.get_joined_right_table().RetrieveColumn(db_schema.schema.CitedCountColumnName)
        compute_object.add_keep_col(cited_count_col)

        if keep_column is not None:
            compute_object.add_keep_col(keep_column, 0)

        df = compute_object.to_list(remove_subj_column)
        #df = dal.datatable_to_dataframe(dt)

        columns = df.columns.tolist()

        # 前面所有欄位(除了最後兩欄)遞增排序,最後一欄遞減排序
        sort_columns = columns[:-2] + [columns[-1]]
        ascending = [True] * len(columns[:-2]) + [False]

        df_sorted = df.sort_values(by=sort_columns, ascending=ascending)

        return df_sorted

@dataclass
class PaperGrowthRateMetric(GrowthRate):
    def paper(self, use_percent_age : bool = True, na_val_notation = None)-> pd.DataFrame:
        return self.calculate_growth_rate(self.main_paper_count(), use_percent_age=use_percent_age, na_val_notation=na_val_notation)

@dataclass 
class Indicator(Metrics):
    @property
    def list_metrics(self) -> PaperList:
        return None
    @property
    def metrics(self) -> PaperMetrics:
        return None
    
    @cached_property
    def hIndex_hcore_cited_count(self) -> pd.DataFrame:   
        return self.list_metrics.cited_count()

    def avg_cited(self, df_cited : pd.DataFrame = None) -> pd.DataFrame:
        df_num = self.metrics.main_paper_count()
        if df_cited is None:      # [Bug fix] `not DataFrame` 會丟 ValueError(truth value is ambiguous)
            df_cited = self.metrics.cited
        
        subj_columns = [f"subj{i}" for i in range(self.subjects.subject_num)]
        df_num.columns = subj_columns + ["Num"]
        df_cited.columns = subj_columns + ["Cited"]

        res = DataAnalysis.a08_cntavg_calculate_join(df_cited, df_num)
        res = res.drop(columns=["Num","Cited"])
        return res

    # def h_index(self) -> pd.DataFrame:
    #     return DataAnalysis.b06_h_index_calculate(self.hIndex_hcore_cited_count)

@dataclass
class PaperIndicator(Indicator):
    @property
    def metrics(self) -> PaperMetrics:
        return PaperMetrics(subjects=self.subjects,get_where_clauses=self.get_where_clauses)
    @property
    def list_metrics(self) -> PaperMetrics:
        return PaperList(subjects=self.subjects,get_where_clauses=self.get_where_clauses)

    