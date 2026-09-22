from abc import ABC
from dataclasses import dataclass, field

from datetime import datetime
from typing import Callable, Generic, Optional, TypeVar, TypeAlias
from pathlib import Path
import pandas as pd
from collections import defaultdict


# PRIS DLL
from dal_provider import get_dal

import common.db_schema as db_schema
import common.util as Util
from components.subjects import Subjects
from components.template import *
from components.template_esi import *
from export.report_exporter import *
from export.output_tab import *
from analysis.metrics import ESIMetrics
from components.esi_field import * 
from exceptions import PRISError

script_dir = Path(__file__).parent.parent
dal = get_dal()

FIELD_VERSION_VALUE: TypeAlias = dict[str, dict[str, str]]
ORG_FIELD_VERSION_VALUE: TypeAlias = dict[str, dict[str, dict[str, str]]]

def try_parse_int(s: str) -> tuple[bool, int]:
    ##"""對應 C# 的 int.TryParse,回傳 (是否成功, 轉換結果)"""
    try:
        return True, int(s)
    except (ValueError, TypeError):
        return False, 0
    
def try_parse_float(string_val)-> tuple[bool, float]:
    try:
        # 成功轉型，回傳 (True, 數值)
        return True, float(string_val)
    except (ValueError, TypeError):
        # 失敗（例如字串是 "abc" 或 None），回傳 (False, 預設值 0.0)
        return False, 0.0


@dataclass
class OrgInfo:
    org_serial: str
    country: str
    org_name_ch: str
    org_name_en: str

class IResettable(ABC):
    reset_request_time: Optional[datetime] = None  # 對應 static DateTime,所有子類別共用

T = TypeVar("T")

class ResettableLazy(IResettable, Generic[T]):
    def __init__(self, value_factory: Callable[[], T]):
        self._factory = value_factory
        self._last_reset_time: Optional[datetime] = None
        self._cached_value: Optional[T] = None # impl
        self._has_value: bool = False

    @property
    def value(self) -> T:
        self._init()
        return self._cached_value

    def _init(self):
        needs_rebuild = (
            self._last_reset_time is None
            or not self._has_value
            or (
                IResettable.reset_request_time is not None
                and self._last_reset_time < IResettable.reset_request_time
            )
        )

        if needs_rebuild:
            self._cached_value = self._factory()
            self._has_value = True
            self._last_reset_time = datetime.now()


def try_get(map:ORG_FIELD_VERSION_VALUE, org_serial: str, ver:str, field:str = "1"):
    return map.get(org_serial, {}).get(field,{}).get(ver,"")


class PresidentESIReport:
    TemplateTypeName: dict[str, TemplateType] = {
        "E1. 近十一年學術論文總數及排名": TemplateType.E1,
        "E2. 近十一年學術論文被引次數及排名": TemplateType.E2,
        "E3. 近十一年學術論文平均被引次數及排名": TemplateType.E3,
        "E4. 近十一年高被引論文數及排名": TemplateType.E4,
        "E5. 近十一年熱門論文數": TemplateType.E5,
        "E6. 近十一年分領域論文數及世界排名、亞太排名": TemplateType.E6,
        "E7. 近十一年分領域被引次數及世界排名、亞太排名": TemplateType.E7,
        "F1. 進入ESI排名之領域及其學術論文數": TemplateType.F1,
        "F2. 進入ESI排名之領域及其學術論文數(亞太排名)": TemplateType.F2,
        "F3. 進入ESI排名之領域及其論文被引次數與平均被引次數": TemplateType.F3,
        "F4. 進入ESI排名之領域及其論文被引次數與平均被引次數(亞太排名)": TemplateType.F4,
        "F5. 各領域論文數前三名機構": TemplateType.F5,
        "F6. 各領域被引次數前三名機構": TemplateType.F6,
    }
    TemplateTypeShortName: dict[str, TemplateType] = { 
        "E1": TemplateType.E1 ,
        "E2": TemplateType.E2 ,
        "E3": TemplateType.E3 ,
        "E4": TemplateType.E4 ,
        "E5": TemplateType.E5 ,
        "E6": TemplateType.E6 ,
        "E7": TemplateType.E7 ,
        "F1": TemplateType.F1 ,
        "F2": TemplateType.F2 ,
        "F3": TemplateType.F3 ,
        "F4": TemplateType.F4 ,
        "F5": TemplateType.F5 ,
        "F6": TemplateType.F6 
    }
    project_name: str = ""
    shown_time: str = ""
    items : list["PresidentESIReportItem"] = field(default_factory=list)
    output_path : str = ""

    def set_items(self, adds):
        self.items = adds


@dataclass
class PresidentESIReportItem:
    Name: str
    Type: TemplateType
    Index: int = 0
    numCHArr = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]

    def __str__(self) -> str:
        return f"{self.Name} | {self.Type.value}"

    def to_sheet_name(self, esi_report : PresidentESIReport) -> str:
        result = self.Name.replace("[專案名]", esi_report.project_name)
        result = result.replace("[表N]", f"表{self.get_num_ch(self.Index)}、")
        result = result.replace("[時間]", esi_report.shown_time)
        return result
    
    def get_num_ch(self,i) -> str:
        if (i <=0 or i >= 100):
            raise PRISError(f"表單Index數值不正確，{i}，正確範圍1~99")
        return Util.get_num_ch(i)

@dataclass
class Anaysis:
    name : str = ""
    subjects : Subjects = None

@dataclass
class FieldSubjectType:
    subject : "Subject"
    bind_cols : dict[str, "Column"]
    selected_values : list[str]
    shown_by_esiid : bool = False


@dataclass
class PresidentESIAnalysis(Anaysis):
    main_ver : str = ""
    comp_ver : str = ""
    main_ver_short : str = ""
    comp_ver_short : str = ""
    get_where_clauses: Callable[["Table"], list["Where"]] = None

    def __post_init__(self):
        self._esi_field_info = None
        self._all_fields_subj = ResettableLazy(self._fetch_all_fields_subj)
        self._sub_fields_subj = ResettableLazy(self._fetch_sub_fields_subj)

        self._org_infos = ResettableLazy(self._fetch_get_org_infos)
        self._selected_orgs = ResettableLazy(self._fetch_get_orgs)
        self._maj_field_id_to_name = ResettableLazy(self._fetch_maj_field_id_to_name)
        self._sub_field_id_to_name = ResettableLazy(self._fetch_sub_field_id_to_name)
        
        self._all_field_esi_metrics = ResettableLazy(self._fetch_all_field_esi_metrics)
        self._sub_field_esi_metrics = ResettableLazy(self._fetch_sub_field_esi_metrics)
        self._maj_fields_and_sub_fields = ResettableLazy(self._fetch_maj_fields_and_sub_fields)
        self._maj_fields_name_and_sub_fields_name = ResettableLazy(self._fetch_maj_fields_name_and_sub_fields_name)
        
        self._paper_count_all_fields = ResettableLazy(self._fetch_pcount_all)
        self._paper_count_world_rank_all_fields = ResettableLazy(self._fetch_pcount_world_rank_all)
        self._paper_count_asiap_rank_all_fields = ResettableLazy(self._fetch_pcount_asiap_rank_all) 

        self._cited_all_fields = ResettableLazy(self._fetch_cited_all)
        self._cited_world_rank_all_fields = ResettableLazy(self._fetch_cited_world_rank_all)
        self._cited_asia_pacific_rank_all_fields = ResettableLazy(self._fetch_cited_asia_pacific_rank_all) 

        self._avg_cited_all_fields = ResettableLazy(self._fetch_avg_cited_all_fields) 

        self._hici_all_fields = ResettableLazy(self._fetch_hici_all_fields) 

        self._hot_all_fields = ResettableLazy(self._fetch_hot_all_fields)
        
        self._paper_count_by_sub_fields = ResettableLazy(self._fetch_paper_count_by_sub_fields)
        self._paper_count_world_rank_by_sub_fields = ResettableLazy(self._fetch_paper_count_world_rank_by_sub_fields)
        self._paper_count_asia_pacific_rank_by_sub_fields = ResettableLazy(self._fetch_paper_count_asia_pacific_rank_by_sub_fields)

        self._cited_threshold_by_fields = ResettableLazy(self._fetch_cited_threshold_by_fields)
        self._world_avg_cited_by_fields = ResettableLazy(self._fetch_world_avg_cited_by_fields)
        self._cited_by_sub_fields = ResettableLazy(self._fetch_cited_by_sub_fields)
        self._avg_cited_by_sub_fields = ResettableLazy(self._fetch_avg_cited_by_sub_fields)
        self._cited_world_rank_by_sub_fields = ResettableLazy(self._fetch_cited_world_rank_by_sub_fields)
        self._cited_asia_pacific_rank_by_sub_fields = ResettableLazy(self._fetch_cited_asia_pacific_rank_by_sub_fields)

        self._field_paper_count_top3Org = ResettableLazy(self._fetch_field_paper_count_top3Org)
        self._field_cited_top3Org = ResettableLazy(self._fetch_field_cited_top3Org)

        if not self.name:
            self.name = "ESI Data"

    @property
    def maj_fields_metrics(self) -> ESIMetrics:
        return ESIMetrics(subjects=self.subjects, get_where_clauses=self.get_where_clauses)
    
    @property
    def selected_orgs_str(self) -> list[str]:
        return self.subjects.selectedVal1
    @property
    def selected_field_str(self) -> list[str]:
        if self._esi_field_info is None:
            self._esi_field_info = self._fetch_esi_field_info()
        return self.subjects.selectedVal2
    ### ==== ALL
    @property
    def all_fields_subj(self):
        return self._all_fields_subj.value
    @property
    def sub_fields_subj(self):
        return self._sub_fields_subj.value
    
    @property
    def org_infos(self) -> dict[str, OrgInfo]:
        return self._org_infos.value
    @property
    def selected_orgs(self) -> list[OrgInfo]:
        return self._selected_orgs.value
    @property
    def maj_field_id_to_name(self) -> dict[str,str]:
        return self._maj_field_id_to_name.value
    @property
    def sub_field_id_to_name(self) -> dict[str,str]:
        return self._sub_field_id_to_name.value
    @property
    def maj_fields_name_and_sub_fields_name(self)-> list[tuple[str,list[str]]]:
        return self._maj_fields_name_and_sub_fields_name.value
    @property
    def all_field_esi_metrics(self) -> ESIMetrics:
        return self._all_field_esi_metrics.value
    @property
    def sub_field_esi_metrics(self) -> ESIMetrics:
        return self._sub_field_esi_metrics.value
    @property
    def all_field_subject(self):
        return self._all_fields_subj.value
    @property
    def maj_fields_and_sub_fields(self) -> list[tuple[str, list[str]]]:
        return self._maj_fields_and_sub_fields.value
    @property
    def cited_threshold_by_fields(self) -> dict[str,str]:
        return self._cited_threshold_by_fields.value
    @property
    def world_avg_cited_by_fields(self) -> dict[str,str]:
        return self._world_avg_cited_by_fields.value
    
    ### ==== E1
    @property
    def paper_count_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_all_fields.value
    @property
    def paper_count_world_rank_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_world_rank_all_fields.value
    @property
    def paper_count_asiap_rank_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_asiap_rank_all_fields.value
    ### ==== E2
    @property
    def cited_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_all_fields.value
    @property
    def cited_world_rank_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_world_rank_all_fields.value
    @property
    def cited_asia_pacific_rank_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_asia_pacific_rank_all_fields.value
    ### ==== E3
    @property
    def avg_cited_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._avg_cited_all_fields.value
    ### ==== E4
    @property
    def hici_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._hici_all_fields.value
    ### ==== E5
    @property
    def hot_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._hot_all_fields.value
    ### ==== F1、F2
    @property
    def paper_count_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_by_sub_fields.value
    @property
    def paper_count_world_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_world_rank_by_sub_fields.value
    @property
    def paper_count_asia_pacific_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._paper_count_asia_pacific_rank_by_sub_fields.value   
    ### ==== F3、F4
    @property
    def cited_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_by_sub_fields.value
    @property
    def avg_cited_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._avg_cited_by_sub_fields.value
    @property
    def cited_world_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_world_rank_by_sub_fields.value
    @property
    def cited_asia_pacific_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        return self._cited_asia_pacific_rank_by_sub_fields.value
    ### ==== F5、F6
    @property
    def field_paper_count_top3Org(self) -> dict[str, list[str]]:
        return self._field_paper_count_top3Org.value
    @property
    def field_cited_top3Org(self) -> dict[str, list[str]]:
        return self._field_cited_top3Org.value


    # 原本是在FieldPanel執行的，把值拉到Analysis存放
    def _fetch_esi_field_info(self) -> ESIFieldValueInfo:

        cmd_str = (f"SELECT GRP.{db_schema.schema.GroupNameColumnName}, INFO.{db_schema.schema.FieldNameCHColumnName}, INFO.{db_schema.schema.FIDColumnName} FROM {db_schema.schema.PaperFieldGroupTableName} GRP "
                   f"INNER JOIN {db_schema.schema.PaperFieldInfoTableName} INFO ON GRP.{db_schema.schema.FGIDColumnName} = INFO.{db_schema.schema.FGIDColumnName}")
        q_res = dal.query_2d_raw(cmd_str)

        return ESIFieldValueInfo(query_list=q_res)

    ## done! 20260814
    def _fetch_get_org_infos(self) -> dict[str,OrgInfo]:
        ## """對應原本要抓取 selectedOrgs 資料的邏輯,只有第一次讀取才會被呼叫"""
        str_cmd = (
            f"SELECT {db_schema.schema.OrgSerialColumnName}, {db_schema.schema.OrgNameENColumnName}, {db_schema.schema.OrgNameCHColumnName}, {db_schema.schema.CountryNameCHColumnName} "
            f"FROM {db_schema.schema.OrgFirstTableName} Org INNER JOIN {db_schema.schema.NationTableName} Nation ON Org.{db_schema.schema.CountryColumnName} = Nation.{db_schema.schema.CountryNameENColumnName}"
        )
        res_dict: dict[str, OrgInfo] = {}
        org_rows = dal.query_2d_raw(str_cmd)
        for row in org_rows:
            new_org = OrgInfo(row[0], row[3], row[2], row[1])
            res_dict[row[0]] = new_org

        return res_dict

    ## done! 20260814
    def _fetch_get_orgs(self) -> list[OrgInfo]:
        ## """對應原本要抓取 selectedOrgs 資料的邏輯,只有第一次讀取才會被呼叫"""
        return [self.org_infos[x] for x in self.selected_orgs_str]

    def _fetch_maj_field_id_to_name(self) -> dict[str,str]:
        return {str(k): v.field_name for k, v in self._esi_field_info.fid_to_field.items()}

    def _fetch_sub_field_id_to_name(self) -> dict[str,str]:
        cmd_str = f"SELECT {db_schema.schema.ESIIDColumnName}, ESI_Name_EN FROM AC_Manager.dbo.Category_ESI"
        q_res = dal.query_2d_raw(cmd_str)
        return { q[0].strip() : self.to_title(q[1]).strip() for q in q_res}
        
    def _fetch_all_field_esi_metrics(self) -> ESIMetrics:
        from components.subjects import copy_subjects
        m = self.maj_fields_metrics
        subjs = copy_subjects(m.subjects)
        # 要留意 C# 的 UseInstitutionSubject 沒處理，讓他恆為true
        subjs.subject2 = self.all_field_subject.subject
        subjs.subj2BindCol = self.all_field_subject.bind_cols
        subjs.selectedVal2 = self.all_field_subject.selected_values
        subjs.ShownByESI_ID |= self.all_field_subject.shown_by_esiid
        m.subjects = subjs

        return m
    # getSubFieldsMetrics()
    def _fetch_sub_field_esi_metrics(self) -> ESIMetrics:
        from components.subjects import copy_subjects
        m = self.maj_fields_metrics
        subjs = copy_subjects(m.subjects)
        # 要留意 C# 的 UseInstitutionSubject 沒處理，讓他恆為true
        subjs.subject2 = self.sub_fields_subj.subject
        subjs.subj2BindCol = self.sub_fields_subj.bind_cols
        subjs.selectedVal2 = self.sub_fields_subj.selected_values
        subjs.ShownByESI_ID |= self.sub_fields_subj.shown_by_esiid
        m.subjects = subjs

        return m

    # 對應 getAllFieldsSubjects
    def _fetch_all_fields_subj(self):
        selected_vals = ["1"]
        subj, bind_cols, selected_val, _,_= db_schema.schema.ESIFieldInfo.get_subject(selected_values=selected_vals)

        return FieldSubjectType(subject=subj, bind_cols=bind_cols, selected_values=selected_val)
    
    # getSubFieldsSubjects
    def _fetch_sub_fields_subj(self):
        selected_vals = self.subjects.selectedVal2
        shown_by_esiid = True
        subj, bind_cols, selected_val ,_,_ = db_schema.schema.ESIFieldInfo.get_subject(selected_values=selected_vals,shown_by_esiid=shown_by_esiid)
        return FieldSubjectType(subject=subj, bind_cols=bind_cols, selected_values=selected_val,shown_by_esiid=shown_by_esiid)

    ## getMajFieldsAndSubFields() / return list[tuple(str,list[str])]
    def _fetch_maj_fields_and_sub_fields(self) :
        fields = self.selected_field_str
        cmd_str = f"SELECT {db_schema.schema.FIDColumnName}, {db_schema.schema.ESIIDColumnName} FROM {db_schema.schema.PaperFieldESITableName}"

        query_res = dal.query_2d_raw(cmd_str)
        res_dict = defaultdict(list)
        for x in query_res:
            fid = x[0]
            esi = x[1]

            if fid in fields:
                res_dict[fid].append(esi)

        res = list(res_dict.items())
        return res

    def _fetch_maj_fields_name_and_sub_fields_name(self):
        name_list = [
            (
                self.maj_field_id_to_name[maj_id] if maj_id in self.maj_field_id_to_name else "",
                [self.sub_field_id_to_name[sub_id] if sub_id in self.sub_field_id_to_name else "" for sub_id in sub_ids]
            ) 
            for maj_id, sub_ids in self.maj_fields_and_sub_fields
        ]
        return name_list
    
    ### E1
    ## getPaperCountAllFields() => parse(allFieldMetrics.PaperCount())
    def _fetch_pcount_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"58191", "2025-03-13":"57453"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.paper_count)
        return res

    ## getPaperCountWorldRankAllFields() => => parse(allFieldMetrics.WorldPaperCountRank())
    def _fetch_pcount_world_rank_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"173", "2025-03-13":"162"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.world_paper_count_rank)
        return res
        

    ## getPaperCountAsiaPacificRankAllFields() => parse(allFieldMetrics.AsiaPacificPaperCountRank())
    def _fetch_pcount_asiap_rank_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"52", "2025-03-13":"45"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.asia_pacific_paper_count_rank)
        return res

    ### E2
    ## getCitedAllFields() => parse(allFieldMetrics.PaperCited())
    def _fetch_cited_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"58191", "2025-03-13":"57453"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.cited)
        return res

    ## getCitedWorldRankAllFields() => parse(allFieldMetrics.WorldCitedRank())
    def _fetch_cited_world_rank_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"173", "2025-03-13":"162"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.world_cited_rank)
        return res
        

    ## getCitedAsiaPacificRankAllFields() => parse(allFieldMetrics.AsiaPacificCitedRank())
    def _fetch_cited_asia_pacific_rank_all(self) -> ORG_FIELD_VERSION_VALUE:
        # res : ORG_FIELD_VERSION_VALUE = {
        #     "TWU000001" : {"1" : {"2026-03-12":"52", "2025-03-13":"45"}},...
        # }
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.asia_pacific_cited_rank)
        return res
    ### E3
    ## getAvgCitedAllFields() => parse(allFieldMetrics.AvgCited())
    def _fetch_avg_cited_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.avg_cited)
        return res
    ### E4
    ## getHiCiAllFields() => parse(allFieldMetrics.Hici())
    def _fetch_hici_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.hici)
        return res
    ### E5
    ### getHotAllFields() => parse(allFieldMetrics.Hot())
    def _fetch_hot_all_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.all_field_esi_metrics.hot)
        return res

    ### F1、F2
    def _fetch_paper_count_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.paper_count)
        return res
    def _fetch_paper_count_world_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.world_paper_count_rank)
        return res
    def _fetch_paper_count_asia_pacific_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.asia_pacific_paper_count_rank)
        return res

    ### F3、F4
    def _fetch_cited_threshold_by_fields(self) -> dict[str,str]:
        cmd_str = (
            f"SELECT {db_schema.schema.ESICategoryColumnName}, MIN({db_schema.schema.CiteColumnName}) AS Threshold "
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} WHERE {db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_short}' "
            f"GROUP BY {db_schema.schema.ESICategoryColumnName}"
        )
        q_res = dal.query_2d_raw(cmd_str)
        return { str(q[0]) : str(q[1]) for q in q_res}
    
    def _fetch_world_avg_cited_by_fields(self) -> dict[str,str]:
        cmd_str = (
            f"SELECT {db_schema.schema.ESICategoryColumnName}, "
            f"CAST(SUM({db_schema.schema.CiteColumnName}) AS float) / CAST(SUM({db_schema.schema.PaperCountColumnName}) as float) AS AvgCited "
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} "
            f"WHERE ({db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_short}') "
            f"GROUP BY {db_schema.schema.ESICategoryColumnName}"
        )
        q_res = dal.query_2d_raw(cmd_str)
        return { str(q[0]) : str(q[1]) for q in q_res}
    
    def _fetch_cited_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.cited)
        return res   
    def _fetch_avg_cited_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.avg_cited)
        return res
    def _fetch_cited_world_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.world_cited_rank)
        return res
    def _fetch_cited_asia_pacific_rank_by_sub_fields(self) -> ORG_FIELD_VERSION_VALUE:
        res = PresidentESIAnalysis.parse(self.sub_field_esi_metrics.asia_pacific_cited_rank)
        return res

    ### F5、F6
    def get_top_3Org(self, db_col_name : str) -> dict[str, list[str]]:
        cmd_orgs_clause = "', '".join(self.selected_orgs_str)
        cmd_field_clause = ", ".join(sub_id for x in self.maj_fields_and_sub_fields for sub_id in x[1])
        cmd_str = (
            f"SELECT {db_schema.schema.ESICategoryColumnName}, {db_schema.schema.OrgSerialColumnName}, Rank FROM ("
            f"SELECT {db_schema.schema.ESICategoryColumnName}, {db_schema.schema.OrgSerialColumnName}, Total, Rank() OVER (PARTITION BY {db_schema.schema.ESICategoryColumnName} ORDER BY Total DESC) AS Rank FROM ("
            f"SELECT DISTINCT {db_schema.schema.ESICategoryColumnName}, {db_schema.schema.OrgSerialColumnName}, SUM({db_col_name}) AS Total FROM ("
            f"SELECT DISTINCT {db_schema.schema.ESICategoryColumnName}, {db_schema.schema.OrgSerialColumnName}, {db_col_name} "
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} INST INNER JOIN {db_schema.schema.ACFirstTableName} ORG ON INST.{db_schema.schema.InstitutionColumnName} = ORG.{db_schema.schema.ACWordColumnName} "
            f"WHERE {db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_short}' AND "
            f"{db_schema.schema.Time_EndColumnName} IS NULL AND "
            f"{db_schema.schema.ESIACMainColumnName} = 1 AND " +
            f"{db_schema.schema.ESICategoryColumnName} IN ({cmd_field_clause}) AND " +
            f"{db_schema.schema.OrgSerialColumnName} IN ('{cmd_orgs_clause}') " +
            f") O GROUP BY {db_schema.schema.ESICategoryColumnName}, {db_schema.schema.OrgSerialColumnName}" +
            f") S " +
            f") R WHERE Rank <= 3"
        )
        query_res= dal.query_2d_raw(cmd_str)
# return qret.Select(x => new { ESI = x[0], Serial = x[1], Rank = x[2] })
#            .GroupBy(x => x.ESI)
#            .ToDictionary(k => k.Key, v => v.OrderBy(x => x.Rank).Select(x => x.Serial).ToList());
        groups = defaultdict(list)
        for x in query_res:
            groups[x[0]].append({"ESI": x[0], "Serial": x[1], "Rank": x[2]})

        res = {
            key: [item["Serial"] for item in sorted(group, key=lambda item: item["Rank"])]
            for key, group in groups.items()
        }
        return res

    def _fetch_field_paper_count_top3Org(self) -> dict[str, list[str]]:
        return self.get_top_3Org(db_schema.schema.PaperCountColumnName)
    def _fetch_field_cited_top3Org(self) -> dict[str, list[str]]:
        return self.get_top_3Org(db_schema.schema.CiteColumnName)

    ## 計算
    def run(self, report : PresidentESIReport) -> ReportExporter:
        report.shown_time = self.main_ver
        re_export = ReportExporter()

        total = len(report.items) # 進度條用
        for idx, ritem in enumerate(report.items):
            tmpl, rows = self.generate_report(ritem, ritem.to_sheet_name(report))
            re_export.add_item(tmpl, rows)

            if DEBUG:
                # 暫時 - 更新進度條
                percent = (idx + 1) / total
                bar = "█" * int(20 * percent) + "-" * (20 - int(20 * percent))
                print(f"\r處理進度: [{bar}] {int(percent * 100)}%", end="", flush=True)

        print()  # 4. 整個迴圈結束後換行        

        return re_export

    ## 匯出
    def export(self, report : PresidentESIReport, re_export: ReportExporter) -> str:
        print("準備匯出檔案....")
        # 匯出
        now = datetime.now().strftime("%y-%m-%d %H%M%S")
        filename = f"ESI校長報表_{now}"
        output_path = f"{report.output_path}{filename}.xlsx"

        if output_path:
            print(f"你選擇的資料夾:{output_path}")
        else:
            raise PRISError("沒有選擇資料夾")

        re_export.export(output_path)
        return output_path


    def generate_report(self, item : PresidentESIReportItem, sheet_name : str) -> tuple[Template, list[list[str]]] :
        #sheet_name = sheet_name#item.to_sheet_name()
        template_type : TemplateType= item.Type
        idx = item.Index

        builders = {
            TemplateType.E1: lambda: (E1(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e1_rows()),
            TemplateType.E2: lambda: (E2(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e2_rows()),
            TemplateType.E3: lambda: (E3(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e3_rows()),
            TemplateType.E4: lambda: (E4(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e4_rows()),
            TemplateType.E5: lambda: (E5(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e5_rows()),
            TemplateType.E6: lambda: (E6(sheet_name, self.maj_fields_name_and_sub_fields_name, idx), self.get_e6_rows()),
            TemplateType.E7: lambda: (E7(sheet_name, self.maj_fields_name_and_sub_fields_name, idx), self.get_e7_rows()),
            TemplateType.F1: lambda: (F1(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f1_rows()),
            TemplateType.F2: lambda: (F2(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f2_rows()),
            TemplateType.F3: lambda: (F3(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f3_rows()),
            TemplateType.F4: lambda: (F4(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f4_rows()),
            TemplateType.F5: lambda: (F5(sheet_name, idx), self.get_f5_rows()),
            TemplateType.F6: lambda: (F6(sheet_name, idx), self.get_f6_rows()),
        }

        if template_type not in builders:
            # raise ValueError(f"未知的 type:{template_type}")
            #print(f"未知的 type:{template_type}")
            raise PRISError(f"未知的TemplateType:{template_type}")
            #return tmpl, temp_rows

        tmpl, temp_rows = builders[template_type]()
        return tmpl, temp_rows

    def get_e1_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.org_name_ch,
                "NameEN": so.org_name_en,
                "Count_MainVer": try_get(self.paper_count_all_fields, so.org_serial, self.main_ver_short),#self.paper_count_all_fields.get(so.org_serial, {}).get("1",{}).get(self.main_ver_short,""),
                "WorldRank_MainVer" : try_get(self.paper_count_world_rank_all_fields, so.org_serial, self.main_ver_short),#self.paper_count_world_rank_all_fields.get(so.org_serial, {}).get("1",{}).get(self.main_ver_short,""),
                "AsiaRank_MainVer" : try_get(self.paper_count_asiap_rank_all_fields, so.org_serial, self.main_ver_short),#self.paper_count_asiap_rank_all_fields.get(so.org_serial, {}).get("1",{}).get(self.main_ver_short,""),
                "Count_CompVer" : try_get(self.paper_count_all_fields, so.org_serial, self.comp_ver_short),#self.paper_count_all_fields.get(so.org_serial, {}).get("1",{}).get(self.comp_ver_short,""),
                "WorldRank_CompVer":try_get(self.paper_count_world_rank_all_fields, so.org_serial, self.comp_ver_short),#self.paper_count_world_rank_all_fields.get(so.org_serial, {}).get("1",{}).get(self.comp_ver_short,""),
                "AsiaRank_CompVer":try_get(self.paper_count_asiap_rank_all_fields, so.org_serial, self.comp_ver_short),#self.paper_count_asiap_rank_all_fields.get(so.org_serial, {}).get("1",{}).get(self.comp_ver_short,""),
            }
            res.append([
                item["OrgSerial"], 
                item["Country"], 
                item["NameCH"], 
                item["NameEN"], 
                item["Count_CompVer"], 
                item["WorldRank_CompVer"],
                item["AsiaRank_CompVer"],
                item["Count_MainVer"],
                item["WorldRank_MainVer"],
                item["AsiaRank_MainVer"],
                PresidentESIAnalysis.try_diff(item["WorldRank_CompVer"],item["WorldRank_MainVer"]),
                PresidentESIAnalysis.try_diff(item["AsiaRank_CompVer"],item["AsiaRank_MainVer"])
            ])

        return res

    def get_e2_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.org_name_ch,
                "NameEN": so.org_name_en,
                "Cited_MainVer":  try_get(self.cited_all_fields, so.org_serial, self.main_ver_short),
                "WorldRank_MainVer" : try_get(self.cited_world_rank_all_fields, so.org_serial, self.main_ver_short),
                "AsiaRank_MainVer" : try_get(self.cited_asia_pacific_rank_all_fields, so.org_serial, self.main_ver_short),
                "Cited_CompVer" : try_get(self.cited_all_fields, so.org_serial, self.comp_ver_short),
                "WorldRank_CompVer": try_get(self.cited_world_rank_all_fields, so.org_serial, self.comp_ver_short),
                "AsiaRank_CompVer": try_get(self.cited_asia_pacific_rank_all_fields, so.org_serial, self.comp_ver_short),
            }
            res.append([
                item["OrgSerial"], 
                item["Country"], 
                item["NameCH"], 
                item["NameEN"], 
                item["Cited_CompVer"], 
                item["WorldRank_CompVer"],
                item["AsiaRank_CompVer"],
                item["Cited_MainVer"],
                item["WorldRank_MainVer"],
                item["AsiaRank_MainVer"],
                PresidentESIAnalysis.try_diff(item["WorldRank_CompVer"],item["WorldRank_MainVer"]),
                PresidentESIAnalysis.try_diff(item["AsiaRank_CompVer"],item["AsiaRank_MainVer"])
            ])

        return res

    def get_e3_rows(self) -> list[list[str]] :
        main_rank = self.get_rank([(o.org_serial,try_get(self.avg_cited_all_fields, o.org_serial, self.main_ver_short )) for o in self.selected_orgs])
        comp_rank = self.get_rank([(o.org_serial,try_get(self.avg_cited_all_fields, o.org_serial, self.comp_ver_short )) for o in self.selected_orgs])
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.org_name_ch,
                "NameEN": so.org_name_en,
                "AvgCited_MainVer":  try_get(self.avg_cited_all_fields, so.org_serial, self.main_ver_short),
                "Rank_MainVer" : main_rank[so.org_serial],
                "AvgCited_CompVer" : try_get(self.avg_cited_all_fields, so.org_serial, self.comp_ver_short),
                "Rank_CompVer" : comp_rank[so.org_serial]
            }
            res.append([
                item["OrgSerial"], 
                item["Country"], 
                item["NameCH"], 
                item["NameEN"], 
                item["AvgCited_CompVer"], 
                item["Rank_CompVer"],
                item["AvgCited_MainVer"],
                item["Rank_MainVer"],
                PresidentESIAnalysis.try_diff(item["Rank_CompVer"],item["Rank_MainVer"])
            ])

        return res

    def get_e4_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.org_name_ch,
                "NameEN": so.org_name_en,
                "PaperCount_MainVer":  try_get(self.paper_count_all_fields, so.org_serial, self.main_ver_short),
                "HiCi_MainVer" : try_get(self.hici_all_fields, so.org_serial, self.main_ver_short),
                "PaperCount_CompVer" : try_get(self.paper_count_all_fields, so.org_serial, self.comp_ver_short),
                "HiCi_CompVer" : try_get(self.hici_all_fields, so.org_serial, self.comp_ver_short),
            }
            res.append([
                item["OrgSerial"], 
                item["Country"], 
                item["NameCH"], 
                item["NameEN"], 
                item["PaperCount_CompVer"], 
                item["HiCi_CompVer"],
                PresidentESIAnalysis.get_ratio(item["PaperCount_CompVer"], item["HiCi_CompVer"]),
                item["PaperCount_MainVer"],
                item["HiCi_MainVer"],
                PresidentESIAnalysis.get_ratio(item["PaperCount_MainVer"], item["HiCi_MainVer"]),
                PresidentESIAnalysis.get_growth_rate(item["HiCi_CompVer"],item["HiCi_MainVer"])
            ])

        return res
    
    def get_e5_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            res.append([
                so.org_serial,
                so.country,
                so.org_name_ch,
                so.org_name_en,
                try_get(self.hot_all_fields, so.org_serial, self.comp_ver_short),
                try_get(self.hot_all_fields, so.org_serial, self.main_ver_short)
            ])
        return res

    def get_e6_e7_rows(self,
        count_by_sub_fields : ORG_FIELD_VERSION_VALUE,
        world_rank_by_sub_fields:ORG_FIELD_VERSION_VALUE, 
        asia_pacific_rank_by_sub_fields:ORG_FIELD_VERSION_VALUE ) -> list[list[str]]:
        res = []

        for org_info in self.selected_orgs:
            row = [
                org_info.org_serial,
                org_info.country,
                org_info.org_name_ch,
                org_info.org_name_en
            ]
            for maj_field_id, sub_ids in self.maj_fields_and_sub_fields:
                for sub_field_id in sub_ids:
                    count = try_get(count_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    world_rank_main_ver = try_get(world_rank_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    world_rank_comp_ver = try_get(world_rank_by_sub_fields, org_info.org_serial, self.comp_ver_short, sub_field_id)
                    asia_pacific_rank_main_ver = try_get(asia_pacific_rank_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    asia_pacific_rank_comp_ver = try_get(asia_pacific_rank_by_sub_fields, org_info.org_serial, self.comp_ver_short, sub_field_id)
                    world_rank_prog = PresidentESIAnalysis.try_diff(world_rank_comp_ver, world_rank_main_ver)
                    asia_pacific_prog = PresidentESIAnalysis.try_diff(asia_pacific_rank_comp_ver, asia_pacific_rank_main_ver)

                    row += [count,world_rank_main_ver,world_rank_prog,asia_pacific_rank_main_ver,asia_pacific_prog]
            res.append(row)

        return res        
    
    def get_e6_rows(self) -> list[list[str]]:
        return self.get_e6_e7_rows(self.paper_count_by_sub_fields, self.paper_count_world_rank_by_sub_fields,self.paper_count_asia_pacific_rank_by_sub_fields)
    
    def get_e7_rows(self) -> list[list[str]]:
        return self.get_e6_e7_rows(self.cited_by_sub_fields, self.cited_world_rank_by_sub_fields,self.cited_asia_pacific_rank_by_sub_fields)


    def get_f1_f2_rows(self, rank:ORG_FIELD_VERSION_VALUE)-> list[list[str]]:
        res = []
        enter_esi_field_num = [0] * len(self.selected_orgs)

        for maj_field_id, sub_ids in self.maj_fields_and_sub_fields:
            maj_field_name = self.maj_field_id_to_name[maj_field_id]
            res.append([maj_field_name])
            for sub_field_id in sub_ids:
                row = []
                sub_field_name = self.sub_field_id_to_name[sub_field_id]
                row.append(sub_field_name)
                org_idx = 0
                for org_info in self.selected_orgs:
                    count = try_get(self.paper_count_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    rank_main_ver = try_get(rank,org_info.org_serial, self.main_ver_short, sub_field_id)
                    rank_comp_ver = try_get(rank,org_info.org_serial, self.comp_ver_short, sub_field_id)
                    rank_prog = PresidentESIAnalysis.try_diff(rank_comp_ver,rank_main_ver)
                    row += [count, rank_main_ver, rank_prog]

                    if count != "":
                        enter_esi_field_num[org_idx] += 1
                    org_idx += 1
                res.append(row)

        res.append([str(x) for x in enter_esi_field_num])

        return res

    def get_f1_rows(self) -> list[list[str]] :
        return self.get_f1_f2_rows(self.paper_count_world_rank_by_sub_fields)

    def get_f2_rows(self) -> list[list[str]] :
        return self.get_f1_f2_rows(self.paper_count_asia_pacific_rank_by_sub_fields)

    def get_f3_f4_rows(self, rank:ORG_FIELD_VERSION_VALUE) -> list[list[str]] :
        res = []
        enter_maj_field_num = [0] * len(self.selected_orgs)
        enter_sub_field_num = [0] * len(self.selected_orgs)

        for maj_field_id, sub_ids in self.maj_fields_and_sub_fields:
            maj_field_name = self.maj_field_id_to_name[maj_field_id]
            res.append([maj_field_name])

            maj_field_has_val = [False] * len(self.selected_orgs)
            for sub_field_id in sub_ids:
                row = []
                sub_field_name = self.sub_field_id_to_name[sub_field_id]
                thres = self.cited_threshold_by_fields[sub_field_id]
                world_avg_cited = self.world_avg_cited_by_fields[sub_field_id]

                row.extend([sub_field_name, thres, world_avg_cited])

                org_idx = 0
                for org_info in self.selected_orgs:
                    cited = try_get(self.cited_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    rank_main_ver = try_get(rank,org_info.org_serial, self.main_ver_short, sub_field_id)
                    rank_comp_ver = try_get(rank,org_info.org_serial, self.comp_ver_short, sub_field_id)
                    rank_prog = PresidentESIAnalysis.try_diff(rank_comp_ver,rank_main_ver)
                    avg_cited = try_get(self.avg_cited_by_sub_fields, org_info.org_serial, self.main_ver_short, sub_field_id)
                    row += [cited, rank_main_ver, rank_prog, avg_cited]

                    if cited != "":
                        enter_sub_field_num[org_idx] += 1
                        maj_field_has_val[org_idx] = True
                    org_idx += 1
                res.append(row)

            for i, has_value in enumerate(maj_field_has_val):
                if has_value:
                    enter_maj_field_num[i] += 1

        enter_maj_field_num_row = [str(len(self.maj_fields_and_sub_fields))]
        enter_maj_field_num_row += [str(x) for x in enter_maj_field_num]
        res.append(enter_maj_field_num_row)
        res.append([str(x) for x in enter_sub_field_num])
        return res

    def get_f3_rows(self) -> list[list[str]] :
        return self.get_f3_f4_rows(self.cited_world_rank_by_sub_fields)

    def get_f4_rows(self) -> list[list[str]] :
        return self.get_f3_f4_rows(self.cited_asia_pacific_rank_by_sub_fields)

    def get_f5_f6_rows(self, top3 : dict[str, list[str]], world_rank : ORG_FIELD_VERSION_VALUE, asia_pacific_rank : ORG_FIELD_VERSION_VALUE) -> list[list[str]] :
        res = []
        for maj_field_id, sub_ids in self.maj_fields_and_sub_fields:
            maj_field_name = self.maj_field_id_to_name[maj_field_id]
            for sub_field_id in sub_ids:
                sub_field_name = self.sub_field_id_to_name[sub_field_id]
                row = [maj_field_name, sub_field_name]
                if sub_field_id in top3:
                    org_ids = top3[sub_field_id]
                    for org_id in org_ids:
                        org_info = self.org_infos[org_id]
                        name = org_info.org_name_ch
                        wr = try_get(world_rank, org_info.org_serial, self.main_ver_short, sub_field_id)
                        apr = try_get(asia_pacific_rank, org_info.org_serial, self.main_ver_short, sub_field_id)

                        row += [name, wr, apr]

                res.append(row)
        return res
    def get_f5_rows(self) -> list[list[str]] :
        return self.get_f5_f6_rows(self.field_paper_count_top3Org, self.paper_count_world_rank_by_sub_fields, self.paper_count_asia_pacific_rank_by_sub_fields)
    def get_f6_rows(self) -> list[list[str]] :
        return self.get_f5_f6_rows(self.field_cited_top3Org, self.cited_world_rank_by_sub_fields, self.cited_asia_pacific_rank_by_sub_fields)

    ### static Method =============================================================================================
    # 取得相對排名
    @staticmethod
    def get_rank(avg_list : list[tuple[str, str]]) -> dict[str, str]:
        df_col_names = ["key", "value"]
        df = pd.DataFrame(columns=df_col_names)
        nan_vals : set[str] = set()
        rows = []
        for org, val in avg_list:
            parse_res, parse_val = try_parse_float(val)
            if parse_res:
                rows.append([org, val])
            else:
                nan_vals.add(org)

        df = pd.DataFrame(rows, columns=df_col_names)

        df_res = dal.b22_ranking_calculate(df, 0)
        res = dict(zip(df_res["key"].astype(str),df_res["Rank"].astype(str)))
        res.update(dict.fromkeys(nan_vals,""))

        return res

    @staticmethod
    # tryGetIntDiff()
    def try_diff(a, b, nullStr = "") -> str:
        if a is not None and b is not None:
            success_a, int_a = try_parse_int(a)
            success_b, int_b = try_parse_int(b)

            if success_a and success_b :
                return str(int_a-int_b)
            
        return nullStr

    @staticmethod
    def parse(df: pd.DataFrame) -> ORG_FIELD_VERSION_VALUE:
        """
        對應原本 C# 的 parse(DataTable dt),
        只是輸入從 DataTable 換成 DataFrame。
        """
        ret: ORG_FIELD_VERSION_VALUE = {}

        for _, row in df.iterrows():
            org = str(row.iloc[0])
            field = str(row.iloc[1])
            ver = str(row.iloc[2])
            val = str(row.iloc[3])

            if org not in ret:
                ret[org] = {}
            if field not in ret[org]:
                ret[org][field] = {}
            ret[org][field][ver] = val

        return ret

    @staticmethod
    def get_ratio(sum:str, val :str) -> str:
        sp_res, sum_f = try_parse_float(sum)
        vp_res, val_f = try_parse_float(val)
        if sp_res and vp_res and sum_f:
            rat = val_f/sum_f
            rat = f"{rat:.16f}"
            return rat
        return ""

    @staticmethod
    def get_growth_rate(pre_val :str, cur_val :str) -> str:
        pp_res, pre_f = try_parse_float(pre_val)
        cp_res, cur_f = try_parse_float(cur_val)

        if pp_res and cp_res and cur_f:
            rat = (cur_f - pre_f) / pre_f
            rat = f"{rat:.16f}"
            return rat
        return ""

    @staticmethod
    def to_title(s: str) -> str:
        return s.lower().title()