from dataclasses import dataclass

from typing import Callable, TypeAlias
from pathlib import Path
import pandas as pd
from collections import defaultdict

# PRIS DLL
from dal_provider import get_dal
from config import DEBUG
import common.db_schema as db_schema
import common.util as Util
import analysis.data_analysis as DataAnalysis
from components import *
from components.template_esi import *
from database import *
from export.report_exporter import *
from analysis.metrics import ESIMetrics
from analysis.base_analysis import Analysis, ResettableLazy
from exceptions import PRISError


script_dir = Path(__file__).parent.parent
dal = get_dal()

FIELD_VERSION_VALUE: TypeAlias = dict[str, dict[str, str]]
ORG_FIELD_VERSION_VALUE: TypeAlias = dict[str, dict[str, dict[str, str]]]



@dataclass
class FieldSubjectType:
    subject : "Subject"                 # 條件 暫存表
    bind_cols : dict[str, "Column"]     # 暫存表Join的欄位
    selected_values : list[str]         # 條件的值
    shown_by_esiid : bool = False       # show esi id


@dataclass
class PresidentESIAnalysis(Analysis):
    main_ver : str = ""         # 主要版本年份區間，x-y年
    comp_ver : str = ""         # 比較版本年份區間，x-y年
    main_ver_key : str = ""     # 主要版本的key 
    comp_ver_key : str = ""     # 比較版本的key
    get_where_clauses: Callable[["Table"], list["Where"]] = None    # 額外的where條件

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

        self._field_paper_count_top_N_Org = ResettableLazy(self._fetch_field_paper_count_top_N_Org)
        self._field_cited_top_N_Org = ResettableLazy(self._fetch_field_cited_top_N_Org)


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
    def org_infos(self) -> dict[str,PaperOrg]:
        return self._org_infos.value
    @property
    def selected_orgs(self) -> list[PaperOrg]:
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
    def field_paper_count_top_N_Org(self) -> dict[str, list[str]]:
        return self._field_paper_count_top_N_Org.value
    @property
    def field_cited_top_N_Org(self) -> dict[str, list[str]]:
        return self._field_cited_top_N_Org.value


    # 原本是在FieldPanel執行的，把值拉到Analysis存放
    def _fetch_esi_field_info(self) -> ESIFieldValueInfo:

        cmd_str = (f"SELECT GRP.{db_schema.schema.GroupNameColumnName}, INFO.{db_schema.schema.FieldNameCHColumnName}, INFO.{db_schema.schema.FIDColumnName} FROM {db_schema.schema.PaperFieldGroupTableName} GRP "
                   f"INNER JOIN {db_schema.schema.PaperFieldInfoTableName} INFO ON GRP.{db_schema.schema.FGIDColumnName} = INFO.{db_schema.schema.FGIDColumnName}")
        q_res = dal.query_2d_raw(cmd_str)

        return ESIFieldValueInfo(query_list=q_res)

    ## done! 20260814
    def _fetch_get_org_infos(self) -> dict[str,PaperOrg]:
        ## """對應原本要抓取 selectedOrgs 資料的邏輯,只有第一次讀取才會被呼叫"""
        str_cmd = (
            f"SELECT {db_schema.schema.OrgSerialColumnName}, {db_schema.schema.OrgNameENColumnName}, {db_schema.schema.OrgNameCHColumnName}, {db_schema.schema.CountryNameCHColumnName} "
            f"FROM {db_schema.schema.OrgFirstTableName} Org INNER JOIN {db_schema.schema.NationTableName} Nation ON Org.{db_schema.schema.CountryColumnName} = Nation.{db_schema.schema.CountryNameENColumnName}"
        )
        res_dict: dict[str, PaperOrg] = {}
        org_rows = dal.query_2d_raw(str_cmd)
        for row in org_rows:
            new_org = PaperOrg(org_serial=row[0], name_ch=row[2], name_en=row[1], country=row[3])
            res_dict[row[0]] = new_org

        return res_dict

    ## done! 20260814
    def _fetch_get_orgs(self) -> list[PaperOrg]:
        ## """對應原本要抓取 selectedOrgs 資料的邏輯,只有第一次讀取才會被呼叫"""
        return [self.org_infos[x] for x in self.selected_orgs_str]

    def _fetch_maj_field_id_to_name(self) -> dict[str,str]:
        return {str(k): v.field_name for k, v in self._esi_field_info.fid_to_field.items()}

    def _fetch_sub_field_id_to_name(self) -> dict[str,str]:
        cmd_str = f"SELECT {db_schema.schema.ESIIDColumnName}, ESI_Name_EN FROM AC_Manager.dbo.Category_ESI"
        q_res = dal.query_2d_raw(cmd_str)
        return { q[0].strip() : Util.str_to_title(q[1]).strip() for q in q_res}
        
    def _fetch_all_field_esi_metrics(self) -> ESIMetrics:
        import copy
        m = self.maj_fields_metrics
        subjs = copy.deepcopy(m.subjects)
        # 要留意 C# 的 UseInstitutionSubject 沒處理，讓他恆為true
        subjs.subject2 = self.all_field_subject.subject
        subjs.subj2BindCol = self.all_field_subject.bind_cols
        subjs.selectedVal2 = self.all_field_subject.selected_values
        subjs.ShownByESI_ID |= self.all_field_subject.shown_by_esiid
        m.subjects = subjs

        return m
    # getSubFieldsMetrics()
    def _fetch_sub_field_esi_metrics(self) -> ESIMetrics:
        import copy
        m = self.maj_fields_metrics
        subjs = copy.deepcopy(m.subjects)
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
            fid = str(x[0])
            esi = str(x[1])

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
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} WHERE {db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_key}' "
            f"GROUP BY {db_schema.schema.ESICategoryColumnName}"
        )
        q_res = dal.query_2d_raw(cmd_str)
        return { str(q[0]) : str(q[1]) for q in q_res}
    
    def _fetch_world_avg_cited_by_fields(self) -> dict[str,str]:
        cmd_str = (
            f"SELECT {db_schema.schema.ESICategoryColumnName}, "
            f"CAST(SUM({db_schema.schema.CiteColumnName}) AS float) / CAST(SUM({db_schema.schema.PaperCountColumnName}) as float) AS AvgCited "
            f"FROM {db_schema.schema.ESIRawDataForInstitutionTableName} "
            f"WHERE ({db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_key}') "
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
            f"WHERE {db_schema.schema.ESIUpdateTimeColumnName} = '{self.main_ver_key}' AND "
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
            field = str(x[0])
            groups[field].append({"ESI": field, "Serial": x[1], "Rank": x[2]})

        res = {
            key: [item["Serial"] for item in sorted(group, key=lambda item: item["Rank"])]
            for key, group in groups.items()
        }
        return res

    def _fetch_field_paper_count_top_N_Org(self) -> dict[str, list[str]]:
        return self.get_top_N_Org(db_schema.schema.PaperCountColumnName)
    def _fetch_field_cited_top_N_Org(self) -> dict[str, list[str]]:
        return self.get_top_N_Org(db_schema.schema.CiteColumnName)

    ## 計算
    def run(self, report : PresidentESIReport) -> ReportExporter:
        report.shown_time = self.main_ver
        re_export = ReportExporter()

        total = len(report.items) # 進度條用
        for idx, ritem in enumerate(report.items):
            tmpl, rows = self.generate_report(ritem, ritem.to_sheet_header_name(report))
            re_export.add_item(tmpl, rows)

            if DEBUG:
                # 暫時 - 更新進度條
                percent = (idx + 1) / total
                bar = "█" * int(20 * percent) + "-" * (20 - int(20 * percent))
                print(f"\r處理進度: [{bar}] {int(percent * 100)}%", end="", flush=True)

        print()  # 4. 整個迴圈結束後換行        

        return re_export

    # 產出報表的數據
    def generate_report(self, item : PresidentESIReportItem, sheet_name : str) -> tuple[Template, list[list[str]]] :
        template_type : TemplateType= item.Type
        idx = item.Index

        builders = {
            TemplateType.E1: lambda: (E1(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e1_rows()), # ESI全領域論文總數及排名 
            TemplateType.E2: lambda: (E2(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e2_rows()), # ESI全領域論文被引次數及排名
            TemplateType.E3: lambda: (E3(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e3_rows()), # ESI全領域論文平均被引次數及排名
            TemplateType.E4: lambda: (E4(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e4_rows()), # ESI高被引論文數及比率 
            TemplateType.E5: lambda: (E5(sheet_name, self.main_ver, self.comp_ver, idx), self.get_e5_rows()), # ESI熱門論文數
            TemplateType.E6: lambda: (E6(sheet_name, self.maj_fields_name_and_sub_fields_name, idx), self.get_e6_rows()), # ESI分領域論文總數及排名
            TemplateType.E7: lambda: (E7(sheet_name, self.maj_fields_name_and_sub_fields_name, idx), self.get_e7_rows()), # ESI分領域論文被引次數及排名
            TemplateType.F1: lambda: (F1(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f1_rows()), # ESI分領域論文總數及世界排名
            TemplateType.F2: lambda: (F2(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f2_rows()), # ESI分領域論文總數及亞太排名
            TemplateType.F3: lambda: (F3(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f3_rows()), # ESI分領域論文被引次數、平均被引次數及世界排名
            TemplateType.F4: lambda: (F4(sheet_name, self.main_ver, self.selected_orgs, idx), self.get_f4_rows()), # ESI分領域論文被引次數、平均被引次數及亞太排名
            TemplateType.F5: lambda: (F5(sheet_name, idx), self.get_f5_rows()), # ESI分領域論文總數前3名
            TemplateType.F6: lambda: (F6(sheet_name, idx), self.get_f6_rows()), # ESI分領域論文被引次數前3名
        }

        if template_type not in builders:
            raise PRISError(f"未知的TemplateType:{template_type}")

        tmpl, temp_rows = builders[template_type]() # 執行並產生報表的資料存到template裡面
        return tmpl, temp_rows

    def get_e1_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.name_ch,
                "NameEN": so.name_en,
                "Count_MainVer": PresidentESIAnalysis.try_get(self.paper_count_all_fields, so.org_serial, self.main_ver_key),
                "WorldRank_MainVer" : PresidentESIAnalysis.try_get(self.paper_count_world_rank_all_fields, so.org_serial, self.main_ver_key),
                "AsiaRank_MainVer" : PresidentESIAnalysis.try_get(self.paper_count_asiap_rank_all_fields, so.org_serial, self.main_ver_key),
                "Count_CompVer" : PresidentESIAnalysis.try_get(self.paper_count_all_fields, so.org_serial, self.comp_ver_key),
                "WorldRank_CompVer":PresidentESIAnalysis.try_get(self.paper_count_world_rank_all_fields, so.org_serial, self.comp_ver_key),
                "AsiaRank_CompVer":PresidentESIAnalysis.try_get(self.paper_count_asiap_rank_all_fields, so.org_serial, self.comp_ver_key),
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
                "NameCH": so.name_ch,
                "NameEN": so.name_en,
                "Cited_MainVer": PresidentESIAnalysis.try_get(self.cited_all_fields, so.org_serial, self.main_ver_key),
                "WorldRank_MainVer" :PresidentESIAnalysis.try_get(self.cited_world_rank_all_fields, so.org_serial, self.main_ver_key),
                "AsiaRank_MainVer" :PresidentESIAnalysis.try_get(self.cited_asia_pacific_rank_all_fields, so.org_serial, self.main_ver_key),
                "Cited_CompVer" :PresidentESIAnalysis.try_get(self.cited_all_fields, so.org_serial, self.comp_ver_key),
                "WorldRank_CompVer":PresidentESIAnalysis.try_get(self.cited_world_rank_all_fields, so.org_serial, self.comp_ver_key),
                "AsiaRank_CompVer":PresidentESIAnalysis.try_get(self.cited_asia_pacific_rank_all_fields, so.org_serial, self.comp_ver_key),
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
        main_rank = self.get_rank([(o.org_serial,PresidentESIAnalysis.try_get(self.avg_cited_all_fields, o.org_serial, self.main_ver_key )) for o in self.selected_orgs])
        comp_rank = self.get_rank([(o.org_serial,PresidentESIAnalysis.try_get(self.avg_cited_all_fields, o.org_serial, self.comp_ver_key )) for o in self.selected_orgs])
        res = []
        for so in self.selected_orgs :
            item = {
                "OrgSerial": so.org_serial,
                "Country": so.country,
                "NameCH": so.name_ch,
                "NameEN": so.name_en,
                "AvgCited_MainVer":  PresidentESIAnalysis.try_get(self.avg_cited_all_fields, so.org_serial, self.main_ver_key),
                "Rank_MainVer" : main_rank[so.org_serial],
                "AvgCited_CompVer": PresidentESIAnalysis.try_get(self.avg_cited_all_fields, so.org_serial, self.comp_ver_key),
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
                "NameCH": so.name_ch,
                "NameEN": so.name_en,
                "PaperCount_MainVer": PresidentESIAnalysis.try_get(self.paper_count_all_fields, so.org_serial, self.main_ver_key),
                "HiCi_MainVer" :PresidentESIAnalysis.try_get(self.hici_all_fields, so.org_serial, self.main_ver_key),
                "PaperCount_CompVer" :PresidentESIAnalysis.try_get(self.paper_count_all_fields, so.org_serial, self.comp_ver_key),
                "HiCi_CompVer" :PresidentESIAnalysis.try_get(self.hici_all_fields, so.org_serial, self.comp_ver_key),
            }
            res.append([
                item["OrgSerial"], 
                item["Country"], 
                item["NameCH"], 
                item["NameEN"], 
                item["PaperCount_CompVer"], 
                item["HiCi_CompVer"],
                Util.get_ratio(item["PaperCount_CompVer"], item["HiCi_CompVer"]),
                item["PaperCount_MainVer"],
                item["HiCi_MainVer"],
                Util.get_ratio(item["PaperCount_MainVer"], item["HiCi_MainVer"]),
                Util.get_growth_rate(item["HiCi_CompVer"],item["HiCi_MainVer"])
            ])

        return res
    
    def get_e5_rows(self) -> list[list[str]] :
        res = []
        for so in self.selected_orgs :
            res.append([
                so.org_serial,
                so.country,
                so.name_ch,
                so.name_en,
               PresidentESIAnalysis.try_get(self.hot_all_fields, so.org_serial, self.comp_ver_key),
               PresidentESIAnalysis.try_get(self.hot_all_fields, so.org_serial, self.main_ver_key)
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
                org_info.name_ch,
                org_info.name_en
            ]
            for _, sub_ids in self.maj_fields_and_sub_fields:
                for sub_field_id in sub_ids:
                    count =PresidentESIAnalysis.try_get(count_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
                    world_rank_main_ver =PresidentESIAnalysis.try_get(world_rank_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
                    world_rank_comp_ver =PresidentESIAnalysis.try_get(world_rank_by_sub_fields, org_info.org_serial, self.comp_ver_key, sub_field_id)
                    asia_pacific_rank_main_ver =PresidentESIAnalysis.try_get(asia_pacific_rank_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
                    asia_pacific_rank_comp_ver =PresidentESIAnalysis.try_get(asia_pacific_rank_by_sub_fields, org_info.org_serial, self.comp_ver_key, sub_field_id)
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
                    count =PresidentESIAnalysis.try_get(self.paper_count_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
                    rank_main_ver =PresidentESIAnalysis.try_get(rank,org_info.org_serial, self.main_ver_key, sub_field_id)
                    rank_comp_ver =PresidentESIAnalysis.try_get(rank,org_info.org_serial, self.comp_ver_key, sub_field_id)
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
                    cited =PresidentESIAnalysis.try_get(self.cited_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
                    rank_main_ver =PresidentESIAnalysis.try_get(rank,org_info.org_serial, self.main_ver_key, sub_field_id)
                    rank_comp_ver =PresidentESIAnalysis.try_get(rank,org_info.org_serial, self.comp_ver_key, sub_field_id)
                    rank_prog = PresidentESIAnalysis.try_diff(rank_comp_ver,rank_main_ver)
                    avg_cited =PresidentESIAnalysis.try_get(self.avg_cited_by_sub_fields, org_info.org_serial, self.main_ver_key, sub_field_id)
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

    def get_f5_f6_rows(self, top_list : dict[str, list[str]], world_rank : ORG_FIELD_VERSION_VALUE, asia_pacific_rank : ORG_FIELD_VERSION_VALUE) -> list[list[str]] :
        res = []
        for maj_field_id, sub_ids in self.maj_fields_and_sub_fields:
            maj_field_name = self.maj_field_id_to_name[maj_field_id]
            for sub_field_id in sub_ids:
                sub_field_name = self.sub_field_id_to_name[sub_field_id]
                row = [maj_field_name, sub_field_name]
                if sub_field_id in top_list:
                    org_ids = top_list[sub_field_id]
                    for org_id in org_ids:
                        org_info = self.org_infos[org_id]
                        name = org_info.name_ch
                        wr =PresidentESIAnalysis.try_get(world_rank, org_info.org_serial, self.main_ver_key, sub_field_id)
                        apr =PresidentESIAnalysis.try_get(asia_pacific_rank, org_info.org_serial, self.main_ver_key, sub_field_id)

                        row += [name, wr, apr]

                res.append(row)
        return res
    def get_f5_rows(self) -> list[list[str]] :
        return self.get_f5_f6_rows(self.field_paper_count_top_N_Org, self.paper_count_world_rank_by_sub_fields, self.paper_count_asia_pacific_rank_by_sub_fields)
    def get_f6_rows(self) -> list[list[str]] :
        return self.get_f5_f6_rows(self.field_cited_top_N_Org, self.cited_world_rank_by_sub_fields, self.cited_asia_pacific_rank_by_sub_fields)

    ### static Method =============================================================================================
    # 取得相對排名
    @staticmethod
    def get_rank(avg_list : list[tuple[str, str]]) -> dict[str, str]:
        df_col_names = ["key", "value"]
        df = pd.DataFrame(columns=df_col_names)
        nan_vals : set[str] = set()
        rows = []
        for org, val in avg_list:
            parse_res, parse_val = Util.try_parse(val, float, 0.0) #try_parse_float(val)
            if parse_res:
                rows.append([org, val])
            else:
                nan_vals.add(org)

        df = pd.DataFrame(rows, columns=df_col_names)

        df_res = DataAnalysis.b22_ranking_calculate(df, 0)
        res = dict(zip(df_res["key"].astype(str),df_res["Rank"].astype(str)))
        res.update(dict.fromkeys(nan_vals,""))

        return res

    @staticmethod
    def try_diff(a, b, nullStr = "") -> str:
        if a is not None and b is not None:
            success_a, int_a = Util.try_parse(a, int, 0)
            success_b, int_b = Util.try_parse(b, int, 0)

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
    def try_get(map:ORG_FIELD_VERSION_VALUE, org_serial: str, ver:str, field:str = "1"):
        return map.get(org_serial, {}).get(field,{}).get(ver,"")


