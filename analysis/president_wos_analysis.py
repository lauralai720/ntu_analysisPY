from dataclasses import dataclass, field

from typing import Callable, TypeAlias
import pandas as pd
from functools import cached_property

# PRIS DLL
from dal_provider import get_dal

import common.db_schema as db_schema
from common.year import Year
import common.util as Util
from components import *
from components.template_wos import *
from export.report_exporter import *
from analysis.metrics import *
from exceptions import PRISError
from analysis.base_analysis import Analysis,ResettableLazy

dal = get_dal()   # [整理] 原本靠 `import *` 連帶帶進來的 dal,改為明確宣告

class WOSTarget(Enum):
    '''報表分析對象Tag，對應呼叫參數target'''
    InternalResearch = 1
    NTUCollege = 2
    NTUCollegeAndDepartment = 3
    Internal = 4
    AsiaPacific = 5


TemplateNameMapping:dict[TemplateType, str|list[str]] = {
    TemplateType.S1 : ["歷年上半年論文數統計","論文數統計"],
    TemplateType.S2 : "論文數統計",
    TemplateType.S3 : "被引次數統計",
    TemplateType.S4 : ["論文成長率","逐年論文成長率"],
    TemplateType.S5 : "平均被引用次數統計",
    TemplateType.S6 : "論文數及成長率",
    TemplateType.S7 : "高影響期刊係數前{0}%及{1}%論文數",
    TemplateType.S8 : "H指數",
    TemplateType.S9 : ["{0}年論文成長率","{0}年論文成長率"],
} 
'''[ TabName(分頁標題), SheetName(表格標題)]，非list的就是一樣的'''

TargetSheetHeader = {
    WOSTarget.InternalResearch : "國內{0}所研究型大學",
    WOSTarget.NTUCollege: "臺灣大學各學院",
    WOSTarget.NTUCollegeAndDepartment : "臺灣大學x各學院系所",
    WOSTarget.Internal : "國內{0}所大學",
    WOSTarget.AsiaPacific : "亞太代表性大學"
}
'''報表分析對象文字，來源自呼叫參數target'''

ORG_MAP: TypeAlias = dict[str, dict[str, float]]
YEAR_MAP: TypeAlias = dict[str, float]

PAPER_COUNT="paper_count"
GROWTH_RATE="growth_rate"



@dataclass(frozen=True)
class ReportOrgInfo:
    """
    「一個機構在報表上要怎麼取資料」的整理結果,S1~S7 與 S9 共用。<br>
    只記錄「用哪個 DB key」,不存數值;數值一律回頭查 paper_count 等(已延遲載入並共用),
    所以不論使用者有沒有跑 S1,S9 都能獨立取得。
    """
    org: str                       # 未合併的 DB key,例如 TWU000001_1900_2300
    org_serial: str                # 機構編碼,例如 TWU000001
    name1: str                     # 機構名稱1 (中文)
    name2: str                     # 機構名稱2 (英文)
    key_by_year: dict | None       # {年份: 該年實際使用的 DB key}; 機構沒有合併設定時為 None
    has_unmerged_row: bool         # 各年使用的 key 不全相同 → (報表上需多一列「*機構編碼」(未合併))


@dataclass
class PresidentWOSAnalysis(Analysis):
    if_val_1:int = WOS_IF_1
    if_val_2:int = WOS_IF_2
    range_year:int = YEAR_RANGE
    get_where_clauses: Callable[["Table"], list["Where"]] = None
    min_year : str = ""
    max_year : str = ""
    merge_org_list : dict = field(default_factory=dict)

    def __post_init__(self):
        self._paper_count = ResettableLazy(self._fetch_paper_count)
        self._first_or_reprint_author_paper_count = ResettableLazy(self._fetch_first_or_reprint_author_paper_count)
        self._cited_count = ResettableLazy(self._fetch_cited_count)
        self._first_or_reprint_author_cited_count = ResettableLazy(self._fetch_first_or_reprint_author_cited_count)
        self._growth_rate = ResettableLazy(self._fetch_growth_rate)
        self._range_year_growth_rate= ResettableLazy(self._fetch_range_year_growth_rate)

        self._avg_cited = ResettableLazy(self._fetch_avg_cited)
        self._scie_data_info = ResettableLazy(self._fetch_scie_data_info)
        self._ssci_data_info = ResettableLazy(self._fetch_ssci_data_info)
        self._ahci_data_info = ResettableLazy(self._fetch_ahci_data_info)

        self._if_1_paper_count = ResettableLazy(self._fetch_if_1_paper_count)
        self._if_2_paper_count = ResettableLazy(self._fetch_if_2_paper_count)
        
        self._first_or_reprint_subject_cache = None   # (subject, bind_cols)

    @cached_property
    def orgs(self) -> list[str] :
        '''DB select 用的 機構Key列表，例如 TWU000001_1900_2300'''
        return list(dict.fromkeys(x.replace("''", "'") for x in self.subjects.subject1.subj_vals))

    @cached_property
    def latest_jrc_year(self) -> int:
        '''從DB取得jcr最近的年份'''
        _jcrVersions = self.get_jcr_version_list()
        return max(_jcrVersions)

    @cached_property
    def selected_range_years(self)->list[str]:
        return Util.get_year_range_list(min_y=int(self.min_year), max_y=int(self.max_year), year_range=self.range_year)

    @cached_property
    def merge_orgs(self) -> dict:
        return self.subjects.WOSselectedVal1.merge_items

    @cached_property
    def report_org_list(self) -> list[ReportOrgInfo]:
        """
        [共用] 把「DB 的 key」整理成「報表上的機構列」。S1~S7 與 S9 原本各自重複這段邏輯
        快取語意與 partial_merge_periods 相同(同一份年份清單下只算一次)。
        """
        org_selected: PaperOrgSelectedValue = self.subjects.WOSselectedVal1
        partial_merge_periods = self.partial_merge_periods
        plans = []
        for org in self.orgs:
            org_serial, start_year, end_year = self._split_orgs(org)
            if (int(start_year), int(end_year)) != (1900, 2300):   # 合併期間專用 key,不單獨成列
                continue
            org_serial, name1, name2 = org_selected.find_org(org_serial)
            key_by_year = partial_merge_periods.get(org_serial, {})
            plans.append(ReportOrgInfo(
                org=org, org_serial=org_serial, name1=name1, name2=name2,
                key_by_year=key_by_year or None,
                has_unmerged_row=bool(key_by_year) and len(set(key_by_year.values())) > 1,
            ))
        return plans
    
    @property
    def years(self) -> list[str] :
        return self.subjects.year.subj_vals
    @property
    def years_without_range(self) -> list[str]:
        return [y for y in self.years if "-" in y]
    @property
    def paper_count(self) -> ORG_MAP:
        return self._paper_count.value
    @property
    def first_or_reprint_author_paper_count(self) -> ORG_MAP :
        return self._first_or_reprint_author_paper_count.value
    @property
    def scie_paper_count(self) -> ORG_MAP:
        return self._scie_data_info.value.get(PAPER_COUNT, {})
    @property
    def ssci_paper_count(self) -> ORG_MAP:
        return self._ssci_data_info.value.get(PAPER_COUNT, {})
    @property
    def ahci_paper_count(self) -> ORG_MAP:
        return self._ahci_data_info.value.get(PAPER_COUNT, {})
    @property
    def if_1_paper_count(self) -> ORG_MAP:
        return self._if_1_paper_count.value
    @property
    def if_2_paper_count(self) -> ORG_MAP:
        return self._if_2_paper_count.value
    @property
    def growth_rate(self) -> ORG_MAP:
        return self._growth_rate.value
    @property
    def range_year_growth_rate(self) -> ORG_MAP:
        return self._range_year_growth_rate.value
    @property
    def scie_growth_rate(self) -> ORG_MAP:
        return self._scie_data_info.value.get(GROWTH_RATE, {})
    @property
    def ssci_growth_rate(self) -> ORG_MAP:
        return self._ssci_data_info.value.get(GROWTH_RATE, {})
    @property
    def ahci_growth_rate(self) -> ORG_MAP:
        return self._ahci_data_info.value.get(GROWTH_RATE, {})

    @property
    def cited_count(self) -> ORG_MAP:
        return self._cited_count.value
    @property
    def first_or_reprint_author_cited_count(self) -> ORG_MAP :
        return self._first_or_reprint_author_cited_count.value
    @property
    def avg_cited(self) -> ORG_MAP:
        return self._avg_cited.value


    # 論文指標 (基礎數據)
    @property
    def paper_metrics(self) -> PaperMetrics:
        return PaperMetrics(subjects=self.subjects, get_where_clauses=self.get_where_clauses)
    # 論文成長率指標
    @property
    def paper_growth_metrics(self) -> PaperGrowthRateMetric:
        return PaperGrowthRateMetric(subjects=self.subjects, get_where_clauses=self.get_where_clauses)
    
    # 文獻計量指標 (評估指標)
    @property
    def paper_indicator_metrics(self) -> PaperIndicator:
        return PaperIndicator(subjects=self.subjects, get_where_clauses=self.get_where_clauses)

    def _get_first_or_reprint_subject(self):
        """
        [優化] 「第一作者/通訊作者」版本的機構暫存表。S2(論文數)與 S3(被引次數)各自呼叫一次,
        原本每次都重新建暫存表並重跑全部機構的 INSERT(等於同一份資料建 3 次);改為只建一次、共用。
        """
        if self._first_or_reprint_subject_cache is None:
            new_subj, new_bind_cols, _, _, _ = db_schema.schema.WOSOrgSubjectInfo.get_subject(
                selected_values=self.subjects.WOSselectedVal1, author_index=AuthorIndex.FirstOrReprint)
            self._first_or_reprint_subject_cache = (new_subj, new_bind_cols)
        return self._first_or_reprint_subject_cache

    def _with_first_or_reprint_subject(self, compute):
        ori_subj = self.subjects.subject1
        ori_bind_col = self.subjects.subj1BindCol
        new_subj, new_bind_cols = self._get_first_or_reprint_subject()
        self.subjects.subject1 = new_subj
        self.subjects.subj1BindCol = new_bind_cols
        try:
            return compute()
        finally: 
            # 出錯也要還原,避免後面的報表用到錯的 subject
            self.subjects.subject1 = ori_subj
            self.subjects.subj1BindCol = ori_bind_col

    def _fetch_paper_count(self):
        df_paper_count = self.paper_metrics.main_paper_count
        res = self.get_orgmap_from_df(df_paper_count)
        return res
    
    def _fetch_first_or_reprint_author_paper_count(self):
        return self._with_first_or_reprint_subject(
            lambda: self.get_orgmap_from_df(self.paper_metrics.main_paper_count))


    def _fetch_cited_count(self):
        df_cited = self.paper_metrics.cited
        res = self.get_orgmap_from_df(df_cited)
        return res
    
    def _fetch_first_or_reprint_author_cited_count(self):
        return self._with_first_or_reprint_subject(
            lambda: self.get_orgmap_from_df(self.paper_metrics.cited))
    
    def _fetch_growth_rate(self):
        df_growth_rate = self.paper_growth_metrics.paper_growth(use_percent_age=False)
        
        res = self.get_orgmap_from_df(df_growth_rate)
        return res  
    
    def _fetch_avg_cited(self):
        df_avg_cited = self.paper_indicator_metrics.avg_cited()
        res = self.get_orgmap_from_df(df_avg_cited)
        return res 

    def _fetch_scie_data_info(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl:Table):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "1", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_scie_paper_count = m.main_paper_count
        df_scie_growth_rate = m.paper_growth(use_percent_age=False)
        res = {
            PAPER_COUNT : self.get_orgmap_from_df(df_scie_paper_count),
            GROWTH_RATE : self.get_orgmap_from_df(df_scie_growth_rate)
        }
        return res

    def _fetch_ssci_data_info(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl:Table):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "2", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses
        df_ssci_paper_count = m.main_paper_count
        df_ssci_growth_rate = m.paper_growth(use_percent_age=False)
        res = {
            PAPER_COUNT : self.get_orgmap_from_df(df_ssci_paper_count),
            GROWTH_RATE : self.get_orgmap_from_df(df_ssci_growth_rate)
        }
        return res

    def _fetch_ahci_data_info(self):
        m = self.paper_growth_metrics
        def get_where_clauses(tbl:Table):
            col_src_db = tbl.GetColumn(db_schema.schema.SourceDBColumnName)
            if col_src_db is None:
                col_src_db = tbl.RetrieveColumn(db_schema.schema.SourceDBColumnName)

            where = dal.create_where_operated_column_to_const(
                col_src_db, dal.OPTYPE.BitwiseAnd, "4", dal.OPTYPE.NotEqual, "0"
            )
            return [where]
        m.get_where_clauses = get_where_clauses

        df_ahci_paper_count = m.main_paper_count
        df_ahci_growth_rate = m.paper_growth(use_percent_age=False)
        res = {
            PAPER_COUNT : self.get_orgmap_from_df(df_ahci_paper_count),
            GROWTH_RATE : self.get_orgmap_from_df(df_ahci_growth_rate)
        }
        return res
    
    def _fetch_first_or_reprint_author_paper_count(self):
        return self._with_first_or_reprint_subject(
            lambda: self.get_orgmap_from_df(self.paper_metrics.main_paper_count))

    def _fetch_first_or_reprint_author_cited_count(self):
        return self._with_first_or_reprint_subject(
            lambda: self.get_orgmap_from_df(self.paper_metrics.cited))

    def _get_if_paper_count(self, prcent_val : float) : 
        m = self.paper_metrics
        if not db_schema.schema.PaperJrcSubjectInfo:
            db_schema.schema.PaperJrcSubjectInfo = PaperJcrIFSubjectInfo()

        selected_val = [self.latest_jrc_year, prcent_val,-1,-1]
        def get_where_clauses(tbl):
            where = self.get_subject_where_clause(db_schema.schema.PaperJrcSubjectInfo, selected_val, tbl)
            return [where]
        m.get_where_clauses = get_where_clauses
        df_if_paper_count = m.main_paper_count
        res = self.get_orgmap_from_df(df_if_paper_count)
        return res
    
    def _fetch_if_1_paper_count(self):
        return self._get_if_paper_count(self.if_val_1/100)

    def _fetch_if_2_paper_count(self):
        return self._get_if_paper_count(self.if_val_2/100)

    def _fetch_range_year_growth_rate(self):
        select_years = self.selected_range_years
        
        merged_paper_count_per_year = {}
        merged_paper_count_range_year = {}

        def add_paper_count_range_year(res:dict, org_serial:str, per_year_vals:list[int]):
            res[org_serial] = {}
            for range_y in select_years:
                (s , e) = map(int, range_y.split("-"))
                total = 0
                for r_y in range(s, e + 1):
                    per_y_val = per_year_vals.get(str(r_y))
                    if per_y_val is None:      # [Bug fix] 原本 `sum + None` → TypeError(且 sum 蓋掉內建函式)
                        raise PRISError(f"年份清單缺少 {r_y},無法計算 {range_y} 的三年論文數")
                    total += per_y_val
                res[org_serial][range_y] = total
        
        def per_year_counts(key_for_year) -> dict:
            return {y: self.paper_count.get(key_for_year(y), {}).get(y, 0) for y in self.years}

        for report_org in self.report_org_list:
            if report_org.key_by_year is None:
                # 沒有合併設定:每年都用原始 key
                merged_paper_count_per_year[report_org.org_serial] = per_year_counts(lambda y: report_org.org)
            else:
                # 有合併設定:每年用 key_by_year 決定的 key
                merged_paper_count_per_year[report_org.org_serial] = per_year_counts(lambda y: report_org.key_by_year[y])
            add_paper_count_range_year(merged_paper_count_range_year, report_org.org_serial, merged_paper_count_per_year[report_org.org_serial])

            if report_org.has_unmerged_row:
                '''如果有部分合併的話'''
                label = f"*{report_org.org_serial}"
                merged_paper_count_per_year[label] = per_year_counts(lambda y: report_org.org)   # 未合併:原始 key
                add_paper_count_range_year(merged_paper_count_range_year, label, merged_paper_count_per_year[label])


        return merged_paper_count_range_year


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

        # 設定報表用的顯示年份
        Template_WOS.set_year_list(self.years)
        Template_WOS.set_range_year_list(self.selected_range_years)
        
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
        Template_WOS.set_rawdata_sheet_suffix(raw_data_str = "Rawdata")

        print("準備匯出檔案....")
        # 匯出
        #now = datetime.now().strftime("%y-%m-%d %H%M%S")
        #filename = f"{report.project_name}_{now}"
        filename = f"{report.project_name}"
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
            TemplateType.S1: lambda: (S1(sheet_name,idx,tab_name), self.get_s1_rows()), # WOS 論文數統計及成長率
            TemplateType.S2: lambda: (S2(sheet_name,idx,tab_name), self.get_s2_rows()), # WOS 論文數統計及FirstAuthorAndReprint論文數及比率
            TemplateType.S3: lambda: (S3(sheet_name,idx,tab_name), self.get_s3_rows()), # WOS 論文被引次數及FirstAuthorAndReprint論文被引次數及比率
            TemplateType.S4: lambda: (S4(sheet_name,idx,tab_name), self.get_s4_rows()), # WOS 論文成長率
            TemplateType.S5: lambda: (S5(sheet_name,idx,tab_name), self.get_s5_rows()), # WOS 平均被引次數統計
            TemplateType.S6: lambda: (S6(sheet_name,idx,tab_name), self.get_s6_rows()), # WOS SCIE、SSCI、A&HCI 各自的論文數及論文成長率
            TemplateType.S7: lambda: (S7(sheet_name,idx,tab_name,self.if_val_1,self.if_val_2), self.get_s7_rows()), # WOS 論文數統計、高影響期刊係數IF值
            #TemplateType.S8: lambda: (S8(sheet_name,idx,tab_name), self.get_s8_rows()), #暫不製作
            TemplateType.S9: lambda: (S9(sheet_name,idx,tab_name), self.get_s9_rows()), # WOS 三年論文成長率
        }

        if template_type not in builders:
            raise PRISError(f"未知的TemplateType:{template_type}")

        tmpl, (temp_rows, basic_rows)= builders[template_type]()
        return tmpl, temp_rows, basic_rows
    
    @cached_property
    def partial_merge_periods(self) -> dict[str, list[tuple[int, int]]]:
        '''
        取得有合併機構編號所要從資料抓取的機構key
        因為要判斷合併起始或結束年份，所以有可能要抓的key不一樣
        例如: TWU000001230100於2021年開始合併TWU000001233300，所以從2021年的資料要抓TWU000001233300_2021_2300
        {2020 : TWU000001230100_1900_2300,2021 : TWU000001230100_2021_2300}
        
        依此類推
        '''
        need_merger_orgs = {}
        for org_serial, year_map in self.merge_orgs.items():
            periods = []

            for year_key in year_map:
                start_year, end_year = map(int, year_key.split("_"))

                if (start_year, end_year) != (1900, 2300):
                    periods.append((start_year, end_year))
                
            if periods:
                need_merger_orgs[org_serial] = periods
        key_by_year = {}
        for k,v in need_merger_orgs.items():
            # 再建立 A 正式列：每年決定要取哪一個 key
            
            key_by_year[k] = {}
            for year in self.years:
                valid_periods = [
                    period
                    for period in v
                    if period[0] <= int(year) <= period[1]
                ]

                if not valid_periods:
                    key_by_year[k][year] = f"{k}_1900_2300"  # A_1900_2300
                    continue

                selected_start, selected_end = max(
                    valid_periods,
                    key=lambda period: period[0],
                )

                key_by_year[k][year] = (
                    f"{k}_{selected_start}_{selected_end}"
                )
        return key_by_year

    def _split_orgs(self, org:str) -> list[tuple[str, str, str]]:
        """共用的前置處理:拆解 org 字串,回傳 (org_serial, name1, name2) 的清單"""
        splited_org = org.split("_")
        return (splited_org[0], splited_org[1], splited_org[2])




    def _build_rows(self, compute_func) -> tuple[list, list]:
        """
        共用的組裝流程,compute_func 是每個 sN 專屬的計算邏輯,
        接收 (org, temp_rows, key_by_year=None),把這筆資料 append 到 temp_rows。
        列順序:有部分年度合併時,先「*機構編碼」(未合併查驗列),再正式列。
        """
        temp_rows = []
        basic_rows = []
        for plan in self.report_org_list:
            if plan.key_by_year is None:
                compute_func(plan.org, temp_rows)
                basic_rows.append([plan.org_serial, plan.name1, plan.name2])
                continue

            if plan.has_unmerged_row:
                compute_func(plan.org, temp_rows)
                basic_rows.append([f"*{plan.org_serial}", plan.name1, plan.name2])

            compute_func(plan.org, temp_rows, plan.key_by_year)
            basic_rows.append([plan.org_serial, plan.name1, plan.name2])
        
        return temp_rows, basic_rows

    def get_s1_rows(self):   
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            res_org_val = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org

                cnt = self.paper_count.get(org_key,{}).get(y, 0)
                gr = self.growth_rate.get(org_key,{}).get(y, "")
                res_org_val.extend([str(cnt),str(gr)])
            temp_rows.append(res_org_val)

        return self._build_rows(compute)

    def get_s2_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            res_org_val = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org

                cnt = self.paper_count.get(org_key,{}).get(y, 0)
                first_or_reprint_author_cnt = self.first_or_reprint_author_paper_count.get(org_key,{}).get(y, 0)
            
                proportion = Util.get_ratio(cnt, first_or_reprint_author_cnt)
                res_org_val.extend([str(cnt),str(first_or_reprint_author_cnt),proportion])
            temp_rows.append(res_org_val)

        return self._build_rows(compute)

    def get_s3_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            res_org_val = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org

                cited = self.cited_count.get(org_key,{}).get(y, 0)
                first_or_reprint_author_cited = self.first_or_reprint_author_cited_count.get(org_key,{}).get(y, 0)
            
                proportion = Util.get_ratio(cited, first_or_reprint_author_cited) #self.get_ratio(first_or_reprint_author_cited, cited)# 0 if cited == 0 else first_or_reprint_author_cited / cited
                res_org_val.extend([str(cited),str(first_or_reprint_author_cited),proportion])
            temp_rows.append(res_org_val)

        return self._build_rows(compute)
 
    def get_s4_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            res_org_val = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org

                gr = self.growth_rate.get(org_key,{}).get(y, "")
                
                res_org_val.append(str(gr))
            temp_rows.append(res_org_val)


        return self._build_rows(compute)

    def get_s5_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            res_org_val = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org
                ac = self.avg_cited.get(org_key,{}).get(y, 0)
                res_org_val.append(str(ac))
            temp_rows.append(res_org_val)

        return self._build_rows(compute)

    def get_s6_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):

            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org
                scie_cnt = self.scie_paper_count.get(org_key, {}).get(y, 0)
                ssci_cnt = self.ssci_paper_count.get(org_key, {}).get(y, 0)
                ahci_cnt = self.ahci_paper_count.get(org_key, {}).get(y, 0)
                scie_gr = self.scie_growth_rate.get(org_key, {}).get(y ,"")
                ssci_gr = self.ssci_growth_rate.get(org_key, {}).get(y ,"")
                ahci_gr = self.ahci_growth_rate.get(org_key, {}).get(y ,"")       
                val_list = [scie_cnt, scie_gr, ssci_cnt, ssci_gr, ahci_cnt, ahci_gr]
                temp_rows.append([str(v) for v in val_list])


        return self._build_rows(compute)

    def get_s7_rows(self):
        def compute(org:str, temp_rows:list, merge_key:dict = None):
            cnt_list = []
            if_1_cnt_list = []
            if_2_cnt_list = []
            for y in self.years:
                if merge_key:
                    org_key = merge_key[y]
                else:
                    org_key = org

                cnt = self.paper_count.get(org_key,{}).get(y, 0)
                if_1_cnt = self.if_1_paper_count.get(org_key,{}).get(y, 0)
                if_2_cnt = self.if_2_paper_count.get(org_key,{}).get(y, 0)

                cnt_list.append(str(cnt))
                if cnt == 0 :
                    if_1_cnt_list.extend(["0","0"])
                    if_2_cnt_list.extend(["0","0"])
                else:
                    if_1_cnt_list.extend([str(if_1_cnt), Util.get_ratio(cnt, if_1_cnt)])
                    if_2_cnt_list.extend([str(if_2_cnt), Util.get_ratio(cnt, if_2_cnt)])

            temp_rows.append(cnt_list)
            temp_rows.append(if_1_cnt_list)
            temp_rows.append(if_2_cnt_list)
            

        return self._build_rows(compute)


    def reset_year_subject(self):
        select_years = Util.get_year_range_list(min_y=int(self.min_year), max_y=int(self.max_year))
        year_selector = WOSYearSelector()
        year_selector.year_list = select_years
        new_subjs, new_bind, _ = year_selector.get_subject()
        years = year_selector.get_years()
        self.subjects.year = new_subjs
        self.subjects.yearBindCol = new_bind
        self.subjects.YearList = years

    def _build_s9_rows(self, compute_func) -> tuple[list, list]:
        """
        S9 的組裝流程。與 _build_rows 的差別:列順序是「正式列在前、*未合併列在後」,
        且 compute_func 只接收列標籤(org_serial 或 *org_serial)。
        """
        temp_rows = []
        basic_rows = []
        for report_org in self.report_org_list:
            compute_func(report_org.org_serial, temp_rows)
            basic_rows.append([report_org.org_serial, report_org.name1, report_org.name2])

            if report_org.has_unmerged_row:
                label = f"*{report_org.org_serial}"
                compute_func(label, temp_rows)
                basic_rows.append([label, report_org.name1, report_org.name2])

        return temp_rows, basic_rows
    
    def get_s9_rows(self):
        '''S9 - self.range_year 年的論文成長率'''
        ## 將年份改成 3年，2年重複的形式(2020-2022、2021-2023...etc)
        select_years = self.selected_range_years
        def compute(org:str, temp_rows:list):
            paper_count_range_year = self.range_year_growth_rate.get(org,{})
            values = [paper_count_range_year[y] for y in select_years]
            # 與 S4 共用 DataAnalysis.calc_growth_rate;第一期與前期為 0 時留白
            temp_rows.append([str(gr) for gr in DataAnalysis.growth_rate_series(values, na_val="")])
        return self._build_s9_rows(compute)


    @staticmethod
    def get_orgmap_from_df(df : pd.DataFrame, skip_years :list[str] = None) -> ORG_MAP:
        '''
        將dataFrame整理成ORG_MAP 
        return {Org_DB_Select_key : {year : val}}
        '''
        res : ORG_MAP = {}

        # [優化] iterrows 每列都建立 Series,改用欄位 zip
        for org, year, val in zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str), df.iloc[:, 2].astype(str)):

            if skip_years and year in skip_years:
                continue

            if org not in res:
                res[org] = {}

            if val == "N/A":
                res[org][year] ="" # C#是null，這邊填空白
            else:
                res[org][year] = float(val)

        return res

            