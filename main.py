"""
主程式進入點。

注意這支檔案完全不需要 import clr、pythonnet、dotnet_setup,
所有 .NET 相關細節都被封裝在 DataAccessLayer 裡面,
main.py 只透過 get_dal() 拿到 DataAccessLayer,呼叫它提供的方法。
"""
import os
print(f"================> MY PYTHON PID: {os.getpid()}")

from rich import print as rprint
import argparse
import win32com.client as win32

#config
from config import *

# PRIS
from pris import run_report
from exceptions import PRISError


def main():
    parser = argparse.ArgumentParser(description="報表匯出工具")
    parser.add_argument("--analysis-type", default = "6", help="分析項目，校長報表(ESI)- 6")
    parser.add_argument("--model-id", required=True, help="模組ID，國內研究型大學- 1, 台大與亞太鄰近大學- 2")
    parser.add_argument("--main-version", required=True, help="主要版本，格式 yyyy-MM-dd")
    parser.add_argument("--compare-version", required=True, help="比較版本，格式 yyyy-MM-dd")
    parser.add_argument("--output-path", default="../PRIS_OUTPUT//", help="輸出檔案路徑")

    if DEBUG:
        analysis_type = DEFAULT_ANALYSIS_TYPE #AnalysisItemType.PaperPresidentReportESI
            
        model_id = DEFAULT_MODEL_ID # 1
        main_version = DEFAULT_MAIN_VER # "2026-03-12" 
        compare_version = DEFAULT_COMP_VER # "2025-03-13"
        output_path = DEFAULT_OUTPUT_PATH # "../PRIS_OUTPUT//"
    else:
        args = parser.parse_args()
        analysis_type = int(args.analysis_type)
        model_id = int(args.model_id)
        main_version = args.main_version
        compare_version = args.compare_version
        output_path = args.output_path

    params = {}
    if analysis_type == 6:
        params = {
            "analysis_type" : analysis_type,
            "model_id" : model_id,
            "main_version" : main_version,
            "compare_version" : compare_version,
            "output_path" : output_path
        }
    elif analysis_type == 4:
        params = {
            "analysis_type" : analysis_type,
            "db_name":"PRIS_WOS_校長報表_202604_2015_2025_260423",
            "file_name": "台大院系所",
            "template_types" :[102, 103, 104, 105, 109],
            #"template_types" :[106,107],
            #"org_ids" : ["TWU000001010000","TWU000001010300","TWU000001065100"],
            "org_ids" : ["TWU000001"],
            #"org_ids" : WOS_ORGS,
            "year_list" : ["2020", "2021","2022","2023","2024", "2025"],
            "target_name" : "臺灣大學各學院",
            "year_format":"x-y年",
            "source_name":"SCI-E、SSCI、A&HCI",
            "output_path" : output_path
        }

    export_file_path = ""
    try:
        #export_file_path = run_report(analysis_type= analysis_type, model_id= model_id, main_version=main_version, compare_version=compare_version, output_path= output_path)
        export_file_path = run_report(**params)
    except PRISError as e:
        rprint(f"[red]{e}[/red]")

    # 處理比對工具要儲存一次才抓的到值的問題
    if export_file_path:
        def evaluate_excel_formulas(file_path):
            # 啟動背景 Excel 應用程式
            absolute_path = os.path.abspath(file_path)
            excel = win32.gencache.EnsureDispatch('Excel.Application')
            excel.Visible = False  # 不顯示視窗
            excel.DisplayAlerts = False  # 關閉警告提示
            
            try:
                # 開啟檔案，這會自動觸發公式計算
                wb = excel.Workbooks.Open(absolute_path)
                wb.Save()  # 儲存計算後的數值
                wb.Close()
            finally:
                excel.Quit()

        # 使用範例
        evaluate_excel_formulas(export_file_path)


if __name__ == "__main__":
    main()
