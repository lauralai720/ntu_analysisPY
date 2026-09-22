from abc import ABC
from dataclasses import dataclass, field

from datetime import datetime
from typing import Callable, TypeAlias
import pandas as pd
from functools import cached_property

# PRIS DLL
from dal_provider import get_dal

import common.db_schema as db_schema
from common.year import Year
from common.util import *
from components.year_selector import WOSYearSelector
from components.template import *
from components.template_wos import *
from components.paper_org_value import AuthorIndex
from components.subject_info import GetSubject, PaperJcrIFSubjectInfo
from export.report_exporter import *
from export.output_tab import *
from analysis.metrics import *
from components.esi_field import * 
from exceptions import PRISError
from analysis.president_esi_analysis import Anaysis,ResettableLazy

class WOSTarget(Enum):
    Internal = 1
    NTUCollege = 2
    NTUCollegeAndDepartment = 3
    AsiaPacific = 4

## [ TabName(分頁標題), SheetName(表格標題)]，非list的就是一樣的
TemplateNameMapping = {
    TemplateType.S1 : ["歷年上半年論文數統計","論文數統計"],
    TemplateType.S2 : "論文數統計",
    TemplateType.S3 : "被引次數統計",
    TemplateType.S4 : ["論文成長率","逐年論文成長率"],
    TemplateType.S5 : "平均被引用次數統計",
    TemplateType.S6 : "論文數及成長率",
    TemplateType.S7 : "高影響期刊係數前15%及40%論文數",
    TemplateType.S8 : "H指數", # 暫時不做
    TemplateType.S9 : ["三年論文成長率","三年論文成長率"],
}


TargetSheetHeader = {
    WOSTarget.Internal : "國內{0}所研究型大學",
    WOSTarget.NTUCollege: "臺灣大學各學院",
    WOSTarget.NTUCollegeAndDepartment : "臺灣大學x各學院系所",
    WOSTarget.AsiaPacific : "亞太代表性大學"
}


ORG_MAP: TypeAlias = dict[str, dict[str, float]]
YEAR_MAP: TypeAlias = dict[str, float]

@dataclass
class PresidentWOSReport:
    project_name: str = "" # file_name
    shown_time: str = ""
    items : list["PresidentWOSReportItem"] = field(default_factory=list)
    year_list : list[str] = field(default_factory=list)
    output_path : str = ""

@dataclass
class PresidentWOSReportItem:
    type : TemplateType
    tab_name: str    # excel 工作表名稱
    sheet_name:str   # 報表上方的名稱
    index: int = 0


@dataclass
class PresidentWOSAnalysis(Anaysis):
    get_where_clauses: Callable[["Table"], list["Where"]] = None
    min_year : str = ""
    max_year : str = ""

    def __post_init__(self):
        self._paper_count = ResettableLazy(self._fetch_paper_count)
        self._first_or_reprint_author_paper_count = ResettableLazy(self._fetch_first_or_reprint_author_paper_count)
        self._cited_count = ResettableLazy(self._fetch_cited_count)
        self._first_or_reprint_author_cited_count = ResettableLazy(self._fetch_first_or_reprint_author_cited_count)
        self._growth_rate = ResettableLazy(self._fetch_growth_rate)
        self._growth_rate_range_year = ResettableLazy(self._fetch_growth_rate_range_year)
        self._growth_rate_without_year = ResettableLazy(self._fetch_growth_rate_without_year)
        self._avg_cited = ResettableLazy(self._fetch_avg_cited)
        self._scie_paper_count = ResettableLazy(self._fetch_scie_paper_count)
        self._ssci_paper_count = ResettableLazy(self._fetch_ssci_paper_count)
        self._ahci_paper_count = ResettableLazy(self._fetch_ahci_paper_count)
        self._scie_growth_rate = ResettableLazy(self._fetch_scie_growth_rate)
        self._ssci_growth_rate = ResettableLazy(self._fetch_ssci_growth_rate)
        self._ahci_growth_rate = ResettableLazy(self._fetch_ahci_growth_rate)
        self._if15_paper_count = ResettableLazy(self._fetch_if15_paper_count)
        self._if40_paper_count = ResettableLazy(self._fetch_if40_paper_count)

    @cached_property
    def orgs(self) -> list[str] :
        return list(dict.fromkeys(x.replace("''", "'") for x in self.subjects.subject1.SubjVals))

    @cached_property
    def latest_jrc_year(self) -> int:
        _jcrVersions = self.get_jcr_version_list()
        return max(_jcrVersions)
    
    @property
    def years(self) -> list[str] :
        return self.subjects.year.SubjVals
    @property
    def years_without_range(self) -> list[str]:
        return [y for y in self.years if "-" in y]
    @property
    def paper_count(self) -> ORG_MAP:
        return self._paper_count.value
    @property
    def scie_paper_count(self) -> ORG_MAP:
        return self._scie_paper_count.value
    @property
    def ssci_paper_count(self) -> ORG_MAP:
        return self._ssci_paper_count.value
    @property
    def ahci_paper_count(self) -> ORG_MAP:
        return self._ahci_paper_count.value
    @property
    def scie_growth_rate(self) -> ORG_MAP:
        return self._scie_growth_rate.value
    @property
    def ssci_growth_rate(self) -> ORG_MAP:
        return self._ssci_growth_rate.value
    @property
    def ahci_growth_rate(self) -> ORG_MAP:
        return self._ahci_growth_rate.value
    @property
    def cited_count(self) -> ORG_MAP:
        return self._cited_count.value
    @property
    
    def growth_rate(self) -> ORG_MAP:
        return self._growth_rate.value
    @property
    def growth_rate_range_year(self) -> ORG_MAP:
        return self._growth_rate_range_year.value
    @property
    def growth_rate_without_year(self) -> ORG_MAP:
        return self._growth_rate_without_year.value
    @property
    def first_or_reprint_author_paper_count(self) -> ORG_MAP :
        return self._first_or_reprint_author_paper_count.value
    @property
    def first_or_reprint_author_cited_count(self) -> ORG_MAP :
        return self._first_or_reprint_author_cited_count.value
    @property
    def avg_cited(self) -> ORG_MAP:
        return self._avg_cited.value
    @property
    def if15_paper_count(self) -> ORG_MAP:
        return self._if15_paper_count.value
    @property
    def if40_paper_count(self) -> ORG_MAP:
        return self._if40_paper_count.value
    @property
    def paper_metrics(self) -> PaperMetrics:
        return PaperMetrics(subjects=self.subjects, get_where_clauses=self.get_where_clauses)

    @property
    def paper_growth_metrics(self) -> PaperGrowthRateMetric:
        return PaperGrowthRateMetric(subjects=self.subjects, get_where_clauses=self.get_where_clauses)
    @property
    def paper_indicator_metrics(self) -> PaperIndicator:
        return PaperIndicator(subjects=self.subjects, get_where_clauses=self.get_where_clauses)

    def _fetch_paper_count(self):
        df_paper_count = self.paper_metrics.main_paper_count()
        res = self.get_orgmap_from_df(df_paper_count)
        return res
    
    def _fetch_cited_count(self):
        df_cited = self.paper_metrics.cited
        res = self.get_orgmap_from_df(df_cited)
        return res
    
    def _fetch_growth_rate(self):
        df_growth_rate = self.paper_growth_metrics.paper(use_percent_age=False)
        res = self.get_orgmap_from_df(df_growth_rate)
        return res  
    
    def _fetch_growth_rate_range_year(self):
        df_growth_rate = self.paper_growth_metrics.paper(use_percent_age=False)
        res = self.get_orgmap_from_df(df_growth_rate)
        return res  

    def _fetch_growth_rate_without_year(self):
        df_growth_rate = self.paper_growth_metrics.paper(use_percent_age=False)
        skip_year_list = self.years_without_range
        res = self.get_orgmap_from_df(df_growth_rate, skip_year_list)
        return res  
    def _fetch_avg_cited(self):
        df_avg_cited = self.paper_indicator_metrics.avg_cited()
        res = self.get_orgmap_from_df(df_avg_cited)
        return res  
    
    def _fetch_scie_paper_count(self):
        m = self.paper_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "1", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_scie_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_scie_paper_count)
        return res

    def _fetch_ssci_paper_count(self):
        m = self.paper_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "2", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_ssci_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_ssci_paper_count)
        return res

    def _fetch_ahci_paper_count(self):
        m = self.paper_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "4", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_ahci_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_ahci_paper_count)
        return res

    def _fetch_scie_growth_rate(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "1", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_scie_growth_rate = m.paper(use_percent_age=False)
        skip_year_list = self.years_without_range
        res = self.get_orgmap_from_df(df_scie_growth_rate, skip_year_list)
        return res

    def _fetch_ssci_growth_rate(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "1", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_ssci_growth_rate = m.paper(use_percent_age=False)
        skip_year_list = self.years_without_range
        res = self.get_orgmap_from_df(df_ssci_growth_rate, skip_year_list)
        return res

    def _fetch_ahci_growth_rate(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "4", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_ahci_growth_rate = m.paper(use_percent_age=False)
        skip_year_list = self.years_without_range
        res = self.get_orgmap_from_df(df_ahci_growth_rate, skip_year_list)
        return res

    def _fetch_first_or_reprint_author_paper_count(self):
        ori_subj = self.subjects.subject1
        ori_bind_col = self.subjects.subj1BindCol

        new_subj, new_bind_cols, _,_,_ = db_schema.schema.WOSOrgSubjectInfo.get_subject(selected_values=self.subjects.WOSselectedVal1,author_index= AuthorIndex.FirstOrReprint)
        self.subjects.subject1 = new_subj
        self.subjects.subj1BindCol = new_bind_cols

        m = self.paper_metrics
        df_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_paper_count)

        self.subjects.subject1 = ori_subj
        self.subjects.subj1BindCol = ori_bind_col

        return res

    def _fetch_first_or_reprint_author_cited_count(self):
        ori_subj = self.subjects.subject1
        ori_bind_col = self.subjects.subj1BindCol

        new_subj, new_bind_cols, _,_,_ = db_schema.schema.WOSOrgSubjectInfo.get_subject(selected_values=self.subjects.WOSselectedVal1,author_index= AuthorIndex.FirstOrReprint)
        self.subjects.subject1 = new_subj
        self.subjects.subj1BindCol = new_bind_cols

        m = self.paper_metrics
        df_cited_count = m.cited
        res = self.get_orgmap_from_df(df_cited_count)

        self.subjects.subject1 = ori_subj
        self.subjects.subj1BindCol = ori_bind_col

        return res
    
    def _fetch_if15_paper_count(self):
        m = self.paper_metrics
        if not db_schema.schema.PaperJrcSubjectInfo:
            db_schema.schema.PaperJrcSubjectInfo = PaperJcrIFSubjectInfo()

        selected_val = [self.latest_jrc_year, 0.15,-1,-1]
        def get_where_clauses(tbl):
            where = self.get_subject_where_clause(db_schema.schema.PaperJrcSubjectInfo, selected_val, tbl)
            return [where]
        m.get_where_clauses = get_where_clauses
        df_if15_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_if15_paper_count)
        return res

    def _fetch_if40_paper_count(self):
        m = self.paper_metrics
        if not db_schema.schema.PaperJrcSubjectInfo:
            db_schema.schema.PaperJrcSubjectInfo = PaperJcrIFSubjectInfo()

        selected_val = [self.latest_jrc_year, 0.40,-1,-1]
        def get_where_clauses(tbl):
            where = self.get_subject_where_clause(db_schema.schema.PaperJrcSubjectInfo, selected_val, tbl)
            return [where]
        m.get_where_clauses = get_where_clauses
        df_if15_paper_count = m.main_paper_count()
        res = self.get_orgmap_from_df(df_if15_paper_count)
        return res

    def get_subject_where_clause(self, subj_info:GetSubject, selected_val : list, table:"Table"):
        subj, subj_dict = subj_info.get_subject(selected_val)
        selected_val = [-1,-1,-1,-1]
        col_pn = table.GetColumn(db_schema.schema.MainBindColumnName)
        where =dal.create_where_column_val_in_subject(col_pn, dal.OPTYPE.In, subj, subj_dict[db_schema.schema.MainBindColumnName])
        return where

    def get_jcr_version_list(self):
        cmd_str = f"SELECT DISTINCT {db_schema.schema.YearColumnName} FROM {db_schema.schema.JcrTableName}"
        query_res = dal.query_2d_raw(cmd_str)
        return [x[0] for x in query_res]


    
    def run(self, report : PresidentWOSReport) -> ReportExporter:

        re_export = ReportExporter()

        int_years = [ ]
        for y in self.subjects.YearList:
            if isinstance(y, Year):
                if y.is_single:
                    int_years.append(y.to_int())
                else:
                    from_y, to_y = y.year
                    int_years.append(to_y)

        self.min_year = str(min(int_years))
        self.max_year = str(max(int_years))
        
        total = len(report.items) # 進度條用
        for idx, ritem in enumerate(report.items):
            tmpl, rows, basic_rows = self.generate_report(ritem)
            re_export.add_item(tmpl, rows, basic_rows)

            if DEBUG:
                # 暫時 - 更新進度條
                percent = (idx + 1) / total
                bar = "█" * int(20 * percent) + "-" * (20 - int(20 * percent))
                print(f"\r處理進度: [{bar}] {int(percent * 100)}%", end="", flush=True)

        print()  # 4. 整個迴圈結束後換行        

        return re_export
    
    ## 匯出
    def export(self, report : PresidentWOSReport, re_export: ReportExporter) -> str:
        Template.set_rawdata_sheet_suffix(raw_data_str = "Rawdata")

        print("準備匯出檔案....")
        # 匯出
        now = datetime.now().strftime("%y-%m-%d %H%M%S")
        filename = f"{report.project_name}_{now}"
        output_path = f"{report.output_path}{filename}.xlsx"

        if output_path:
            print(f"你選擇的資料夾:{output_path}")
        else:
            raise PRISError("沒有選擇資料夾")

        re_export.export_wos(output_path)
        return output_path


    def generate_report(self, item : PresidentWOSReportItem) -> tuple[Template, list[list[str]], list[list[str]]] :
        template_type : TemplateType= item.type
        idx = item.index
        sheet_name = item.sheet_name
        tab_name = item.tab_name
        builders = {
            TemplateType.S1: lambda: (S1(sheet_name,idx,tab_name), self.get_s1_rows()),
            TemplateType.S2: lambda: (S2(sheet_name,idx,tab_name), self.get_s2_rows()),
            TemplateType.S3: lambda: (S3(sheet_name,idx,tab_name), self.get_s3_rows()),
            TemplateType.S4: lambda: (S4(sheet_name,idx,tab_name), self.get_s4_rows()),
            TemplateType.S5: lambda: (S5(sheet_name,idx,tab_name), self.get_s5_rows()),
            TemplateType.S6: lambda: (S6(sheet_name,idx,tab_name), self.get_s6_rows()),
            TemplateType.S7: lambda: (S7(sheet_name,idx,tab_name), self.get_s7_rows()),
            #TemplateType.S8: lambda: (S8(sheet_name), self.get_s8_rows()),
            TemplateType.S9: lambda: (S9(sheet_name,idx,tab_name), self.get_s9_rows()),
        }

        if template_type not in builders:
            # raise ValueError(f"未知的 type:{template_type}")
            #print(f"未知的 type:{template_type}")
            raise PRISError(f"未知的TemplateType:{template_type}")
            #return tmpl, temp_rows

        tmpl, (temp_rows, basic_rows)= builders[template_type]()
        return tmpl, temp_rows, basic_rows

    def get_s1_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]
              
            org_paper_count = self.paper_count.get(org)
            growth_rate_per_year = self.growth_rate_without_year.get(org)
            res_org_val = []
            for y in self.years:
                cnt : float | None = None
                gr : float | None = None
                if org_paper_count:
                    cnt = org_paper_count.get(y)
                if growth_rate_per_year:
                    gr = growth_rate_per_year.get(y)

                res_cnt = cnt if cnt is not None else 0        
                res_org_val.extend([str(res_cnt),str(gr if gr is not None else "")])

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        return temp_rows, basic_rows    

    def get_s2_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]
                
            org_paper_count = self.paper_count.get(org)
            first_or_reprint_author_paper_count_per_year = self.first_or_reprint_author_paper_count.get(org)
            res_org_val = []
            for y in self.years:
                cnt : float | None = None
                first_or_reprint_author_cnt : float | None = None
                if org_paper_count:
                    cnt = org_paper_count.get(y)
                if first_or_reprint_author_paper_count_per_year:
                    first_or_reprint_author_cnt = first_or_reprint_author_paper_count_per_year.get(y)

                res_cnt = cnt if cnt is not None else 0
                res_first_cnt = first_or_reprint_author_cnt if first_or_reprint_author_cnt is not None else 0
                proportion = 0 if res_cnt == 0 else res_first_cnt / res_cnt
                res_org_val.extend([str(res_cnt),str(res_first_cnt),str(proportion)])

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        
        return temp_rows, basic_rows

    def get_s3_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            org_cited_count = self.cited_count.get(org)
            first_or_reprint_author_cited_count_per_year = self.first_or_reprint_author_cited_count.get(org)
            res_org_val = []
            for y in self.years:
                cited : float | None = None
                first_or_reprint_author_cited : float | None = None
                if org_cited_count:
                    cited = org_cited_count.get(y)
                if first_or_reprint_author_cited_count_per_year:
                    first_or_reprint_author_cited = first_or_reprint_author_cited_count_per_year.get(y)

                res_cited = cited if cited is not None else 0
                res_first_cited = first_or_reprint_author_cited if first_or_reprint_author_cited is not None else 0
                proportion = 0 if res_cited == 0 else res_first_cited / res_cited
                res_org_val.extend([str(res_cited),str(res_first_cited),str(proportion)])

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        
        return temp_rows, basic_rows
    
    def get_s4_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            growth_rate_per_year = self.growth_rate.get(org)
            res_org_val = []
            for y in self.years:
                gr :float | None = None
                if growth_rate_per_year:
                    gr = growth_rate_per_year.get(y)
                
                res_org_val.append(str(gr if gr is not None else ""))

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        return temp_rows, basic_rows

    def get_s5_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            org_avg_cited = self.avg_cited.get(org)
            
            res_org_val = []
            for y in self.years:
                ac : float | None = None
                
                if org_avg_cited:
                    ac = org_avg_cited.get(y)

                res_ac = ac if ac is not None else 0
                
                res_org_val.extend([str(res_ac)])

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        
        return temp_rows, basic_rows

    def get_s6_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            scie_paper_count_per_year = self.scie_paper_count.get(org)
            ssci_paper_count_per_year = self.ssci_paper_count.get(org)
            ahci_paper_count_per_year = self.ahci_paper_count.get(org)
            scie_growth_rate_per_year = self.scie_growth_rate.get(org)
            ssci_growth_rate_per_year = self.ssci_growth_rate.get(org)
            ahci_growth_rate_per_year = self.ahci_growth_rate.get(org)
            
            #res_org_val = []
            for y in self.years:
                scie_cnt : float | None = None
                ssci_cnt : float | None = None
                ahci_cnt : float | None = None
                scie_gr : float | None = None
                ssci_gr : float | None = None
                ahci_gr : float | None = None

                if scie_paper_count_per_year:
                    scie_cnt = scie_paper_count_per_year.get(y, 0)
                if ssci_paper_count_per_year:
                    ssci_cnt = ssci_paper_count_per_year.get(y, 0)
                if ahci_paper_count_per_year:
                    ahci_cnt = ahci_paper_count_per_year.get(y, 0)
                if scie_growth_rate_per_year:
                    scie_gr = scie_growth_rate_per_year.get(y ,"")
                if ssci_growth_rate_per_year:
                    ssci_gr = ssci_growth_rate_per_year.get(y ,"")
                if ahci_growth_rate_per_year:
                    ahci_gr = ahci_growth_rate_per_year.get(y ,"")       
                val_list = [scie_cnt, scie_gr, ssci_cnt, ssci_gr, ahci_cnt, ahci_gr]
                temp_rows.append([str(v) for v in val_list])

            #temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        
        return temp_rows, basic_rows

    def get_s7_rows(self):
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            paper_count_per_year = self.paper_count.get(org)
            if15_paper_count_per_year = self.if15_paper_count.get(org)
            if40_paper_count_per_year = self.if40_paper_count.get(org)
            
            #res_org_val = []
            cnt_list = []
            if15_cnt_list = []
            if40_cnt_list = []
            for y in self.years:
                cnt : float | None = None
                if15_cnt : float | None = None
                if40_cnt : float | None = None

                if paper_count_per_year:
                    cnt = paper_count_per_year.get(y, 0)
                if if15_paper_count_per_year:
                    if15_cnt = if15_paper_count_per_year.get(y, 0)
                if if40_paper_count_per_year:
                    if40_cnt = if40_paper_count_per_year.get(y, 0)

                cnt_list.append(str(cnt))
                if cnt == 0 :
                    if15_cnt_list.extend(["0","0"])
                    if40_cnt_list.extend(["0","0"])
                else:
                    if15_cnt_list.extend([str(if15_cnt), str(if15_cnt/cnt)])
                    if40_cnt_list.extend([str(if40_cnt), str(if40_cnt/cnt)])

            temp_rows.append(cnt_list)
            temp_rows.append(if15_cnt_list)
            temp_rows.append(if40_cnt_list)
            basic_rows.append([org_serial, name1, name2])
        
        return temp_rows, basic_rows

    def reset_year_subject(self):
        select_years = get_year_range_list(min_y=int(self.min_year), max_y=int(self.max_year))
        year_selector = WOSYearSelector()
        year_selector.year_list = select_years
        new_subjs, new_bind, _ = year_selector.get_subject()
        years = year_selector.get_years()
        self.subjects.year = new_subjs
        self.subjects.yearBindCol = new_bind
        self.subjects.YearList = years

    def get_s9_rows(self):
        self.reset_year_subject()
        temp_rows = []
        basic_rows = []
        for org in self.orgs:
            splited_org = org.split("\x1c")
            org_serial = splited_org[0]
            name1 = splited_org[1]
            name2 = splited_org[2]

            growth_rate_in_year = self.growth_rate_range_year.get(org)
            res_org_val = []
            for y in self.years:
                gr :float | None = None
                if growth_rate_in_year:
                    gr = growth_rate_in_year.get(y)
                
                res_org_val.append(str(gr if gr is not None else ""))

            temp_rows.append(res_org_val)
            basic_rows.append([org_serial, name1, name2])
        return temp_rows, basic_rows


    @staticmethod
    def get_orgmap_from_df(df : pd.DataFrame, skip_years :list[str] = None) -> ORG_MAP:
        res : ORG_MAP = {}

        for _, row in df.iterrows():
            org = str(row.iloc[0])
            year = str(row.iloc[1])
            val = str(row.iloc[2])

            if skip_years and year in skip_years:
                continue

            if org not in res:
                res[org] = {}

            if val == "N/A":
                res[org][year] ="" # C#是null，這邊填空白
            else:
                res[org][year] = float(val)

        return res

            