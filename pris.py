from rich import print as rprint

#config
from config import *

# PRIS DLL
from dal_provider import get_dal

# PRIS
from analysis.president_esi_analysis import *
from analysis.analysis_type import AnalysisItemType
from components.esi_year import YearSelector, ESIYearStyle
from components.subject_info import *
import common.db_schema as db_schema
from exceptions import PRISError


regReportTableName = "AC_Manager.dbo.RegReportTest" if DEBUG else "AC_Manager.dbo.RegReport"
regReportFieldTableName = "AC_Manager.dbo.RegReport_FieldTest" if DEBUG else "AC_Manager.dbo.RegReport_Field"
regReportOrgTableName = "AC_Manager.dbo.RegReport_OrgTest" if DEBUG else "AC_Manager.dbo.RegReport_Org"
regReportReportTableName = "AC_Manager.dbo.RegReport_tableTest" if DEBUG else "AC_Manager.dbo.RegReport_table" 

def load(rid) -> tuple[list[str], list[str], PresidentESIReport]:
    #load sub
    load_org_res, org_rows = load_orgs(rid)

    load_field_res, field_rows = load_fields(rid)
    #load report
    load_report_res, pesi_report = load_reports(rid)
    
    if load_report_res and load_org_res and load_field_res:
        rprint(f"[green]Load report success![/green]")
    else:
        raise PRISError("report、機構、領域load時，無資料或發生錯誤")

    return org_rows, field_rows, pesi_report

## load 機構
## 004跟005併校，變091 - 20260827
def load_orgs(rid) -> tuple[bool, list[str] | None]:
    dal = get_dal()
    strCmd = f"SELECT DISTINCT OrgSerial FROM {regReportOrgTableName} WHERE RID = '{rid}'"
    query_res = dal.query_2d_raw(strCmd)
    except_orgs = ["TWU000004", "TWU000005"]
    replace_org = "TWU000091"
    res = [r[0] for r in query_res if r[0] != ""]
    for r in query_res:
        if r[0] in except_orgs:
            res.remove(r[0])
            if replace_org not in res:
                res.append(replace_org)
                
    return True, res

## load 領域
def load_fields(rid) -> tuple[bool, list[str] | None]:
    dal = get_dal()
    strCmd = f"SELECT DISTINCT FID FROM {regReportFieldTableName} WHERE RID = '{rid}'"
    res = dal.query_2d_raw(strCmd)
    
    return True,[r[0] for r in res]
    
## load 報表及類型
def load_reports(rid) -> tuple[bool, PresidentESIReport | None]:
    import re

    dal = get_dal()
    print(f"start loadReport : {rid}")
    strCmd = f"SELECT DISTINCT table_setting FROM {regReportReportTableName} WHERE RID = '{rid}'"
    report_rows = dal.query_2d_raw(strCmd) # PRISUtilityKit.DBAL.Cls dll

    report = PresidentESIReport()
    report_items : list[tuple[int, PresidentESIReportItem]] = []
    if not report_rows:
        print("no REPORT")
    else:
        if len(report_rows) <= 0:
            print("empty list")
            return True, report
        else:
            for row in report_rows:
                pattern = re.compile(r"([0-9]+)\. (.*)\| ([EF][0-9]+)$")
                match = pattern.match(row[0])
                
                if match:
                    order = int(match.group(1).strip())
                    name = match.group(2).strip()
                    template_type_str = match.group(3).strip()
                    template_type = PresidentESIReport.TemplateTypeShortName.get(template_type_str)
                    if template_type is None:
                        rprint(f"[red]RegReport_table.RID 為 {rid} 的設定為無法辨識的表單類型 {template_type_str}[/red]")
                        return False, None

                    report_item = PresidentESIReportItem(name, template_type)
                    report_items.append((order,report_item))
                    
                else:
                    rprint(f"[red]RegReport_table.RID 為 {rid} 的設定 \"{row[0]}\" 無法辨識, 請確認正確性[/red]")
                    return False, None

            
            report.items = [item[1] for item in sorted(report_items, key=lambda x: x[0])]
            
            ## 針對Index做變化，原本的邏輯是在getItem才寫上去
            for idx, x in enumerate(report.items):
                x.Index = idx+1
    
    return True, report

## code at Utils.GetSubjects()
def get_subjects( subj1_selected : list[str],subj2_selected : list[str], year_selector : YearSelector) -> Subjects:
    subj1, subj1_bind_col,subj1_header, subj1_type_name  = get_subj1_subject(subj1_selected)
    subj2, subj2_bind_col,subj2_header, subj2_type_name  = get_subj2_subject(subj2_selected)
    subj_year, subj_year_bind_col,subj_year_header = get_year_subject(year_selector=year_selector)
    selected_year = year_selector.get_selected()
    years = [selected_year[0].Version.year, selected_year[1].Version.year]
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
    )

    return subjs

## 機構
def get_subj1_subject(selected_fields:list[str]) -> tuple["Subject",dict[str,"Column"],str, str]:
    subj1_subjinfo = ESIInstitutionSubjectInfo("Institution", "機構")
    db_schema.schema.ESIInstitutionInfo = subj1_subjinfo
    subj, bind_col = subj1_subjinfo.get_subject(selected_values=selected_fields)
    return subj, bind_col, subj1_subjinfo.name, subj1_subjinfo.nameEN
    
## field 領域
def get_subj2_subject(selected_fields:list[str]) -> tuple["Subject",dict[str,"Column"],str, str]:
    subj2_subjinfo = ESIFieldSubjectInfo("Field", "領域")
    db_schema.schema.ESIFieldInfo = subj2_subjinfo
    subj, bind_col = subj2_subjinfo.get_subject(selected_values=selected_fields)
    return subj, bind_col, subj2_subjinfo.name, subj2_subjinfo.nameEN

# 時間
def get_year_subject(year_selector : YearSelector) -> tuple["Subject",dict[str,"Column"],str]:
    subj, bind_col = year_selector.get_subject()
    return subj, bind_col, "版本"


# 跑PRIS 分析項目為 校長報表(ESI)
def run_president_esi_report(model_id:int, main_version: str, comp_version: str, output_path: str = "output/report.xlsx") -> tuple[bool, str]:
    # 互動式選擇年份區間(report_year.py 內部一樣是透過 get_dal() 拿同一份 DataAccessLayer)
    year_selector = YearSelector()
    year_selector.set_versions(main_version,comp_version)

    if year_selector.selected_main is None or year_selector.selected_comp is None:
        #rprint("[red]沒有選擇完整的年份區間,程式結束[/red]")
        raise PRISError(f"沒有選擇完整的年份區間")

    ## 載入模組
    strCmd = f"SELECT RID, R_Name FROM {regReportTableName}"
    model_rows = dal.query_2d_raw(strCmd)

    selected_row = next((model for model in model_rows if int(model[0]) == model_id), None)
    if selected_row is None:
        raise PRISError(f"沒有存在的模組，receive model{model_id}")    
    
    project_name = selected_row[1].strip()

    rprint(f"[green]你選的是:{selected_row[0]} - {project_name}[/green]")

    ## 載入模組及領域、機構等資料
    orgs, fields, esi_report = load(selected_row[0])

    ## 顯示Query後的資料
    print(f"{project_name} 中的 比較年份 : ")
    print(f"主要年份 - {year_selector.selected_main.get_verion_str()}({year_selector.selected_main.to_str(ESIYearStyle.Style2)})")
    print(f"比較年份 - {year_selector.selected_comp.get_verion_str()}({year_selector.selected_comp.to_str(ESIYearStyle.Style2)})")

    if orgs is not None:
        print(f"{project_name} 中的 機構列表 : ")
        for x in orgs:
            print(f"{x}")

    if fields is not None:
        print(f"{project_name} 中的 領域列表 : ")
        for x in fields:
            print(f"{x}")

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

        prESI_anaylsis = PresidentAnalysis(main_ver=s_main_ver,main_ver_short=s_main_ver_short,comp_ver=s_comp_ver,comp_ver_short=s_comp_ver_short)
        
            ## 生成一個可以用的subjects
        all_subjs = get_subjects(subj1_selected=orgs, subj2_selected=fields, year_selector=year_selector)

        prESI_anaylsis.subjects = all_subjs
        prESI_anaylsis.get_where_clauses = lambda table:None # 因為現階段都回傳null，所以暫時給一個方法可以被執行
         
        # run 計算，這邊包含匯出excel
        re_export = prESI_anaylsis.run(esi_report)
        
        if re_export is None:
            raise PRISError("計算完的資料是None")

        # 匯出報表
        prESI_anaylsis.export(report=esi_report, re_export=re_export)


def run_report(analysis_type: int, model_id:int, main_version: str, comp_version: str, output_path: str = "./output//"):

    # 第一次呼叫 get_dal(),這裡才會真正初始化 .NET runtime、載入 DLL
    dal = get_dal()

    # 建立共用的Schema
    db_schema.schema = db_schema.ESISchema()
    
    # 設定連線(整個程式只需要做一次)
    #success = dal.set_connection("140.112.180.160","Lis_User","5566server^.<")
    success = dal.set_connection(DEFAULT_DB_IP, DEFAULT_DB_USER, DEFAULT_DB_PW)
    if not success:
        rprint("[red]連線設定失敗[/red]")
        raise PRISError("DB連線設定失敗")
    
    rprint("[green]DB連線設定成功[/green]")
    
    analysis_type = AnalysisItemType(analysis_type)

    if analysis_type != AnalysisItemType.PaperPresidentReportESI:
        rprint("[red]分析項目目前只有校長報表(ESI),程式結束。[/red]")
        raise PRISError(f"分析項目目前只有校長報表(ESI)，receive type:{analysis_type}")

    # 先判斷路徑是否存在，不存在生成一個資料夾
    if os.path.isdir(output_path):
        rprint("[green]資料夾存在，可以安全存檔！[/green]")
    else:
        rprint(f"[blue]資料夾不存在，建立資料夾: {output_path}[/blue]")
        os.makedirs(output_path)
        rprint(f"[green]已建立資料夾：{output_path}[/green]")


    return run_president_esi_report(
        model_id= model_id,
        main_version= main_version,
        comp_version=comp_version,
        output_path=output_path
    )
    