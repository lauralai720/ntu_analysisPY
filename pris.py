from rich import print as rprint
from typing import Any

#config
from config import *

# PRIS DLL
from dal_provider import get_dal

# PRIS
from analysis.president_esi_analysis import *
from analysis.president_wos_analysis import *
from components import YearSelector,ESIYearSelector,ESIYearStyle, WOSYearSelector,ESIInstitutionSubjectInfo,ESIFieldSubjectInfo,WOSPaperOrgSubjectInfo
import common.db_schema as db_schema
import common.util as Util
from exceptions import PRISError
from database import SQLExecute, DB

dal = get_dal()   # [整理] 原本 run_president_esi_report / insert_integrate_data 用到 dal,卻沒有在本檔宣告(靠 import * 連帶帶入)


# regReportTableName = "AC_Manager.dbo.RegReportTest" if DEBUG else "AC_Manager.dbo.RegReport"
# regReportFieldTableName = "AC_Manager.dbo.RegReport_FieldTest" if DEBUG else "AC_Manager.dbo.RegReport_Field"
# regReportOrgTableName = "AC_Manager.dbo.RegReport_OrgTest" if DEBUG else "AC_Manager.dbo.RegReport_Org"
# regReportReportTableName = "AC_Manager.dbo.RegReport_tableTest" if DEBUG else "AC_Manager.dbo.RegReport_table" 

# ## ESI - load 機構
# ## 004跟005併校，變091 - 20260827
# def load_orgs(rid) -> tuple[bool, list[str] | None]:
#     dal = get_dal()
#     strCmd = f"SELECT DISTINCT OrgSerial FROM {regReportOrgTableName} WHERE RID = '{rid}' ORDER BY OrgSerial"
#     query_res = dal.query_2d_raw(strCmd)
#     except_orgs = ["TWU000004", "TWU000005"]
#     replace_org = "TWU000091"
#     res = [r[0] for r in query_res if r[0] != ""]
#     for r in query_res:
#         if r[0] in except_orgs:
#             res.remove(r[0])
#             if replace_org not in res:
#                 res.append(replace_org)
                
#     return True, res

# ## ESI - load 領域
# def load_fields(rid) -> tuple[bool, list[str] | None]:
#     dal = get_dal()
#     strCmd = f"SELECT DISTINCT FID FROM {regReportFieldTableName} WHERE RID = '{rid}' ORDER BY FID"
#     res = dal.query_2d_raw(strCmd)
    
#     return True,[str(r[0]) for r in res]
    
# ## load 報表及類型
# def load_reports(rid) -> tuple[bool, PresidentESIReport | None]:
#     import re

#     dal = get_dal()
#     print(f"start loadReport : {rid}")
#     strCmd = f"SELECT DISTINCT table_setting FROM {regReportReportTableName} WHERE RID = '{rid}'"
#     report_rows = dal.query_2d_raw(strCmd)

#     report = PresidentESIReport()
#     report_items : list[tuple[int, PresidentESIReportItem]] = []
#     if not report_rows:
#         print("no REPORT")
#     else:
#         if len(report_rows) <= 0:
#             print("empty list")
#             return True, report
#         else:
#             for row in report_rows:
#                 pattern = re.compile(r"([0-9]+)\. (.*)\| ([EF][0-9]+)$")
#                 match = pattern.match(row[0])
                
#                 if match:
#                     order = int(match.group(1).strip())
#                     name = match.group(2).strip()
#                     template_type_str = match.group(3).strip()
#                     template_type = PresidentESIReport.TemplateTypeShortName.get(template_type_str)
#                     if template_type is None:
#                         rprint(f"[red]RegReport_table.RID 為 {rid} 的設定為無法辨識的表單類型 {template_type_str}[/red]")
#                         return False, None

#                     report_item = PresidentESIReportItem(name, template_type)
#                     report_items.append((order,report_item))
                    
#                 else:
#                     rprint(f"[red]RegReport_table.RID 為 {rid} 的設定 \"{row[0]}\" 無法辨識, 請確認正確性[/red]")
#                     return False, None

            
#             report.items = [item[1] for item in sorted(report_items, key=lambda x: x[0])]
            
#             ## 針對Index做變化，原本的邏輯是在getItem才寫上去
#             for idx, x in enumerate(report.items):
#                 x.Index = idx+1
    
#     return True, report

# ## ESI - load 所需資料(機構、領域、模組內的報表列表)
# def load(rid) -> tuple[list[str], list[str], PresidentESIReport]:
#     #load sub
#     load_org_res, org_rows = load_orgs(rid)

#     load_field_res, field_rows = load_fields(rid)
#     #load report
#     load_report_res, pesi_report = load_reports(rid)
    
#     if load_report_res and load_org_res and load_field_res:
#         rprint(f"[green]Load report success![/green]")
#     else:
#         raise PRISError("report、機構、領域load時，無資料或發生錯誤")

#     return org_rows, field_rows, pesi_report

## code at Utils.GetSubjects()

_selected_template_data : dict[int, dict] = None

def get_selected_templates(template_types : list[int])-> dict[int, dict]:
    global _selected_template_data
    if _selected_template_data is not None:
        return _selected_template_data

    dal = get_dal()
    type_list_str = ",".join([str(x) for x in template_types])
    strCmd = f"SELECT DISTINCT {db_schema.schema.ReportTemplateTypeColumn}, {db_schema.schema.ReportAnalysisTypeColumn}, {db_schema.schema.ReportTemplateNameColumn} FROM {db_schema.schema.ReportTemplateTableName} WHERE Type IN ({type_list_str})"
    report_df = dal.query(strCmd)
    if report_df.empty:
        return {}

    dict_val_cols = [db_schema.schema.ReportAnalysisTypeColumn, db_schema.schema.ReportTemplateNameColumn]
    report_dict = report_df.set_index(db_schema.schema.ReportTemplateTypeColumn)[dict_val_cols].to_dict(orient='index')
    _selected_template_data = report_dict

    return _selected_template_data


def get_subjects( subj1_selected: list[str],subj2_selected: list[str], year_selector: YearSelector, subj1_obj:GetSubject, subj2_obj:GetSubject) -> Subjects:
    subj1, subj1_bind_col,select_val1,subj1_header,subj1_type_name  = get_subj1_subject(subj1_selected, subj1_obj)
    subj2, subj2_bind_col,select_val2,subj2_header,subj2_type_name  = get_subj2_subject(subj2_selected, subj2_obj)
    subj_year, subj_year_bind_col,subj_year_header = get_year_subject(year_selector=year_selector)
    selected_year = []
    years = []
    if isinstance(year_selector, ESIYearSelector) :
        selected_year = year_selector.get_selected()
        years = [selected_year[0].Version.year, selected_year[1].Version.year]
    elif isinstance(year_selector, WOSYearSelector):
        years = year_selector.get_years()

    subjs = Subjects(
        subject1= subj1,
        subject2= subj2,
        year= subj_year,
        subj1BindCol=subj1_bind_col,
        subj2BindCol=subj2_bind_col,
        yearBindCol= subj_year_bind_col,
        Subject1Header = subj1_header + "1" if subj1_header is not None else subj1_header,
        Subject2Header = subj2_header + "2" if subj2_header is not None else subj2_header,
        YearHeader= subj_year_header,
        YearList= years,
        selectedVal1=subj1_selected,
        selectedVal2=subj2_selected,
        selectedYear=selected_year,
        Subject1Type=subj1_type_name,
        Subject2Type=subj2_type_name,
        WOSselectedVal1= select_val1,
    )

    return subjs

## 機構
def get_subj1_subject(selected_vals:list[str], subj1_subjinfo:GetSubject) -> tuple["Subject", dict[str,"Column"], Any, str, str]:
    if selected_vals :
        subj, bind_col, select_val, name_ch, name_en = subj1_subjinfo.get_subject(selected_values=selected_vals)
        return subj, bind_col, select_val, name_ch, name_en
    return None, None, None, None, None
    
## field 領域
def get_subj2_subject(selected_vals:list[str], subj2_subjinfo:GetSubject) -> tuple["Subject", dict[str,"Column"], Any, str, str]:
    if selected_vals :
        subj, bind_col, select_val, name_ch, name_en = subj2_subjinfo.get_subject(selected_values=selected_vals)
        return subj, bind_col, select_val, name_ch, name_en
    return None, None, None, None, None

# 時間
def get_year_subject(year_selector : YearSelector) -> tuple["Subject", dict[str,"Column"], str]:
    subj, bind_col, year_str = year_selector.get_subject()
    return subj, bind_col, year_str


def check_esi_year_format(year_list:list[str])-> bool :
    import re
    if len(year_list) < 2 :
        return False
    rgx_esi_version = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if bool(rgx_esi_version.match(year_list[0])) == False or bool(rgx_esi_version.match(year_list[1])) == False:
        return False
    return True

def create_esi_report(template_types:list[int]):

    report_dict = get_selected_templates(template_types)
    report = PresidentESIReport()
    if len(report_dict) <= 0:
        print("empty list")
        return report
    else:
        order = 1
        for t_type in template_types:
            report_info = report_dict.get(t_type)
            if report_info:
                analysis_type = report_info.get("AnalysisType", 0)
                name = report_info.get("ReportName", "")
                if not name or AnalysisItemType(analysis_type) != AnalysisItemType.PaperPresidentReportESI:
                    rprint(f"[red]{t_type}-{analysis_type}的設定為無法辨識的表單類型，請查看AC_Manager.Report_Type[/red]")
                    continue

                report_item = PresidentESIReportItem(name, TemplateType(t_type))
                report_item.Index = order
                report.items.append(report_item)
                order += 1
    
    return report

# 跑PRIS 分析項目為 校長報表(ESI)
#def run_president_esi_report(model_id:int, main_version: str, compare_version: str, output_path: str = "./output/") -> str:
def run_president_esi_report(file_name:str, template_types : list[int], org_ids: list[str], field_ids:list[int], year_list:list[str], output_path: str = "./output/") -> str:

    if not check_esi_year_format(year_list) :
        raise PRISError(f"ESI - 年份數量或不正確，{year_list}")
    main_version = year_list[0]
    compare_version = year_list[1]
    db_schema.schema = db_schema.ESISchema()
    # 互動式選擇年份區間(report_year.py 內部一樣是透過 get_dal() 拿同一份 DataAccessLayer)
    year_selector = ESIYearSelector()
    year_selector.set_versions(main_version,compare_version)

    if year_selector.selected_main is None or year_selector.selected_comp is None:
        #rprint("[red]沒有選擇完整的年份區間,程式結束[/red]")
        raise PRISError(f"沒有選擇完整的年份區間")


    # ## 載入模組及領域、機構等資料
    str_field_ids = [str(f) for f in field_ids]
    esi_report = create_esi_report(template_types)
    project_name = file_name.format(Util.get_num_ch(len(org_ids)))

    ## 顯示Query後的資料
    print(f"{project_name} 中的 比較年份 : ")
    print(f"主要年份 - {year_selector.selected_main.get_verion_str()}({year_selector.selected_main.to_str(ESIYearStyle.Style2)})")
    print(f"比較年份 - {year_selector.selected_comp.get_verion_str()}({year_selector.selected_comp.to_str(ESIYearStyle.Style2)})")


    if esi_report is not None:
        esi_report.output_path = output_path
        esi_report.project_name = project_name
        esi_report.shown_time = year_selector.selected_main.Start
        
        print(f"{project_name} 中的 報表列表 : ")
        for x in esi_report.items:
            print(f"{x.Index}. {x.Name}")

        """ Run 計算 start from MainView.runAnalysis """
        s_main_ver = str(year_selector.selected_main)
        s_main_ver_short = year_selector.selected_main.get_verion_str()
        s_comp_ver = str(year_selector.selected_comp)
        s_comp_ver_short = year_selector.selected_comp.get_verion_str()

        prESI_anaylsis = PresidentESIAnalysis(main_ver=s_main_ver,main_ver_short=s_main_ver_short,comp_ver=s_comp_ver,comp_ver_short=s_comp_ver_short)

        subj1_subjinfo = ESIInstitutionSubjectInfo("Institution", "機構")
        db_schema.schema.ESIInstitutionInfo = subj1_subjinfo
        subj2_subjinfo = ESIFieldSubjectInfo("Field", "領域")
        db_schema.schema.ESIFieldInfo = subj2_subjinfo

        ## 生成一個可以用的subjects
        all_subjs = get_subjects(subj1_selected=org_ids, subj2_selected=str_field_ids, year_selector=year_selector, subj1_obj=subj1_subjinfo, subj2_obj=subj2_subjinfo)

        prESI_anaylsis.subjects = all_subjs
        prESI_anaylsis.get_where_clauses = lambda table:None # 因為現階段都回傳null，所以暫時給一個方法可以被執行
         
        # run 計算，這邊包含匯出excel
        re_export = prESI_anaylsis.run(esi_report)
        
        if re_export is None:
            raise PRISError("計算完的資料是None")

        # 匯出報表
        export_file_path = esi_report.output_file
        re_export.export(export_file_path)
        #export_file_path = prESI_anaylsis.export(report=esi_report, re_export=re_export)

        return export_file_path

# 為了報表整併的ID
integrate_list : dict[str, dict[str, list[str]]] = {
    "TWU000001992127" : {"like" : ["TWU0000012%"], "excluded":["TWU000001220200","TWU000001230300"]},
    "TWU000001992124" : {"like" : ["TWU00000121%", "TWU00000122%", "TWU00000123%", "TWU00000124%"]},
    "TWU000001992527" : {"like" : ["TWU00000121%", "TWU00000125%", "TWU00000126%", "TWU00000127%"]},
    "TWU000001129100" : {"like" : ["TWU0000011291%"]},
    "TWU000001127999" : {"like" : ["TWU000001127%", "TWU0000011254%", "TWU0000011291%"]},
}

def check_wos_integrate_exist() -> bool:
    for key in integrate_list.keys():
        query_cmd = f"SELECT CASE WHEN EXISTS (SELECT 1 FROM {db_schema.schema.Org2ndTableName} WHERE [WOS_ORG_2nd].[Orgname] ='{key}') THEN 1 ELSE 0 END AS [Exists]"
        exist = SQLExecute.do_exist_query(query_cmd)
        if not exist: 
            return False
    return True


def create_wos_report(file_name:str, template_types : list[int], target_name:str, year_format:str, source_name:str, mix_year:int, max_year:int, wos_analysis: PresidentWOSAnalysis) -> PresidentWOSReport:
    report = PresidentWOSReport()
    report.project_name = file_name
    year_range_replace = year_format.replace("x", str(mix_year)).replace("y", str(max_year))
    report_items : list[PresidentWOSReportItem] = []
    for i in range(len(template_types)):
        template_type = TemplateType(template_types[i])
        if isinstance(TemplateNameMapping[template_type], list):
            tab = TemplateNameMapping[template_type][0]
            sheet = TemplateNameMapping[template_type][1]
        else:
            tab = TemplateNameMapping[template_type]
            sheet= TemplateNameMapping[template_type]

        if template_type == TemplateType.S7:
            tab = tab.format(wos_analysis.if_val_1, wos_analysis.if_val_2)
            sheet = sheet.format(wos_analysis.if_val_1, wos_analysis.if_val_2)

        if template_type == TemplateType.S9:
            year_str = Util.get_num_ch(wos_analysis.range_year)
            tab = tab.format(year_str)
            sheet = sheet.format(year_str)

        whole_sheet_name = f"{target_name}{year_range_replace}{source_name}{sheet}"

        report_item = PresidentWOSReportItem(type=template_type, sheet_name=whole_sheet_name, tab_name= tab, index=i)
        report_items.append(report_item)
    
    report.items = report_items
    return report


## template_types S1~S8
def run_president_wos_report(
        db_name: str, 
        file_name:str, 
        template_types : list[int], 
        org_ids: list[str], 
        year_list:list[str], 
        target:int, 
        year_format:str, 
        source_name:str, 
        output_path: str = "./output/", 
        **other) -> str:
    db_schema.schema = db_schema.WOSSchema()
    db_schema.schema.set_DB_name(db_name)
    rprint(f"[green]設定DB名稱 : {db_schema.schema.DBName}[/green]")

    if not org_ids:
        raise PRISError("沒有輸入機構列表，無法分析")
    
    ## 機構
    print(f"輸入機構數量 : {len(org_ids)}")

    if len(org_ids) == 1 and org_ids[0] == "TWU000001":
        ## 要抓台大院系級的再來檢查
        if not check_wos_integrate_exist():
            raise PRISError(f"資料庫沒有整併的資料，請確認是否有執行整併的insert。")

    wos_target = WOSTarget(int(target))
    ## check Sheet標題
    if wos_target not in TargetSheetHeader:
        raise PRISError("找不到Sheet標題.")

    target_name = TargetSheetHeader[wos_target]
    target_name = target_name.format(Util.get_num_ch(len(org_ids)))
    
    ## 年份
    year_selector = WOSYearSelector()
    year_selector.year_list = year_list
    # template 那邊需要年份
    Template_WOS.set_year_list(year_list)

    years = [int(x) for x in year_list if x]
    if not years:
        raise PRISError("年份列表不得為空")

    # 建立分析用的class
    wos_analysis = PresidentWOSAnalysis()
    # 設定部分參數的值(如果沒有就用預設值)
    jcr_if_1 = other.get("jcr_if_1",0)
    jcr_if_2 = other.get("jcr_if_2",0)
    if jcr_if_1 > 0 and jcr_if_1 < 100:
        wos_analysis.if_val_1 = jcr_if_1
    if jcr_if_2 > 0 and jcr_if_2 < 100:
        wos_analysis.if_val_2 = jcr_if_2

    ## 報表
    wos_report = create_wos_report(file_name, template_types, target_name, year_format, source_name, min(years), max(years), wos_analysis)
    wos_report.output_path = output_path

    subj1_subjinfo = WOSPaperOrgSubjectInfo(selected_values=org_ids)
    db_schema.schema.WOSOrgSubjectInfo = subj1_subjinfo
    subj2_subjinfo = None

    ## 生成一個可以用的subjects
    all_subjs = get_subjects(subj1_selected=org_ids, subj2_selected=None, year_selector=year_selector, subj1_obj=subj1_subjinfo, subj2_obj=subj2_subjinfo)
    
    
    wos_analysis.subjects = all_subjs
    

    wos_analysis.get_where_clauses = lambda table:None # 因為現階段都回傳null，所以暫時給一個方法可以被執行

    re_export = wos_analysis.run(wos_report)

    if re_export is None:
        raise PRISError("計算完的資料是None")

    # 匯出報表
            
    export_file_path = wos_report.output_file
    re_export.export_wos(export_file_path)
    #export_file_path = wos_analysis.export(report=wos_report, re_export=re_export)

    return export_file_path


ANALYSIS_KEY = "analysis_type"

def run_report(**kwargs):

    db_conn_success = DB.set_connection(DEFAULT_DB_IP, DEFAULT_DB_USER, DEFAULT_DB_PW)
    if not db_conn_success:
        rprint("[red]PY DB連線設定失敗[/red]")
        raise PRISError("PY DB連線設定失敗")

    if ANALYSIS_KEY not in kwargs :
        rprint("[red]沒有輸入分析項目,程式結束。[/red]")
        raise PRISError(f"沒有輸入分析項目")

    analysis_type = AnalysisItemType(int(kwargs[ANALYSIS_KEY]))
    
    kwargs.pop(ANALYSIS_KEY, None) 

    if "output_path" not in kwargs :
        output_path = "./"
    else:
        output_path = kwargs["output_path"]

    # 先判斷路徑是否存在，不存在生成一個資料夾
    os.makedirs(output_path, exist_ok=True)      # [整理] 避免 isdir 與 makedirs 之間的競態

    try:
        if analysis_type == AnalysisItemType.PaperPresidentReportESI:
            return run_president_esi_report(**kwargs)
        elif analysis_type == AnalysisItemType.PaperPresidentReport:
            return run_president_wos_report(**kwargs)
        else:
            rprint("[red]分析項目目前只有校長報表ESI/WOS,程式結束。[/red]")
            raise PRISError(f"分析項目目前只有校長報表ESI/WOS，receive type:{analysis_type}")
    finally:
        # [優化] 報表結束(成功或失敗)就清掉本次建立的 #暫存表,避免連線存活期間 tempdb 持續累積
        SQLExecute.drop_temp_tables()



# 為了報表整併的ID
integrate_list : dict[str, dict[str, list[str]]] = {
    "TWU000001992127" : {"like" : ["TWU0000012%"], "excluded":["TWU000001220200","TWU000001230300"]},
    "TWU000001992124" : {"like" : ["TWU00000121%", "TWU00000122%", "TWU00000123%", "TWU00000124%"]},
    "TWU000001992527" : {"like" : ["TWU00000121%", "TWU00000125%", "TWU00000126%", "TWU00000127%"]},
    "TWU000001129100" : {"like" : ["TWU0000011291%"]},
    "TWU000001127999" : {"like" : ["TWU000001127%", "TWU0000011254%", "TWU0000011291%"]},
}

# 需要整併的資料，在出WOS報表前請先insert
def insert_integrate_data(db_name:str):

    db_conn_success = DB.set_connection(DEFAULT_DB_IP, DEFAULT_DB_USER, DEFAULT_DB_PW)
    if not db_conn_success:
        rprint("[red]PY DB連線設定失敗[/red]")
        raise PRISError("PY DB連線設定失敗")
    
    rprint("[green]DB連線設定成功[/green]")

    db_schema.schema = db_schema.WOSSchema()
    db_schema.schema.set_DB_name(db_name)

    for key, data in integrate_list.items():
        rprint(f"[white]處理 {key} 的insert[/white]")
        cmd = f"INSERT INTO {db_schema.schema.Org2ndTableName} SELECT DISTINCT [ISI_ID],[AddressIndex],'{key}' AS Orgname,[Country],[Reprint] FROM {db_schema.schema.Org2ndTableName} "

        like_list = data.get("like", [])
        if like_list:
            like_str = " OR ".join([f"[OrgName] LIKE N'{like_o}'" for like_o in like_list])
            if key == "TWU000001992127":
                excluded_ids = data.get("excluded", [])
                if excluded_ids:
                    excluded_str = ",".join([f"'{exclude_o}'" for exclude_o in excluded_ids])
                    cmd += f"WHERE ({like_str} and [OrgName] NOT IN ({excluded_str})) "
            else:
                cmd += f"WHERE ({like_str}) "

        if key == "TWU000001127999" :
            cmd += f"AND ISI_ID NOT IN (SELECT ISI_ID FROM {db_schema.schema.Org2ndTableName} WHERE  [WOS_ORG_2nd].[Orgname] ='{key}' )"
        else:
            cmd += f"AND NOT EXISTS (SELECT * FROM {db_schema.schema.Org2ndTableName} WHERE [ISI_ID] = [WOS_ORG_2nd].[ISI_ID] AND [WOS_ORG_2nd].[Orgname] ='{key}' )"
        #print(cmd)
        dal.do_no_query(cmd)
        rprint(f"[white]{key} 的insert處理完畢。[/white]")
    
    rprint("[green]前置作業，insert完成。[/green]")

if __name__ == "__main__":
    insert_integrate_data("PRIS_WOS_校長報表_202604_2015_2025_260423")