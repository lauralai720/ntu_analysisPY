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
import sys


#config
from config import *

# PRIS
from pris import run_report
from exceptions import PRISError


def main():
    parser = argparse.ArgumentParser(description="報表匯出工具")
    parser.add_argument("--analysis-type", required=True, default = 6,type=int, help="分析項目，校長報表(WOS)- 4 / 校長報表(ESI)- 6")
    parser.add_argument("--model-id",type=int,help="模組ID，國內研究型大學- 1, 台大與亞太鄰近大學- 2")
    parser.add_argument("--main-version", help="主要版本，格式 yyyy-MM-dd")
    parser.add_argument("--compare-version", help="比較版本，格式 yyyy-MM-dd")
    parser.add_argument("--output-path", required=True, default="../PRIS_OUTPUT//", help="輸出檔案路徑")
    parser.add_argument("--years",nargs="+",type=str)
    parser.add_argument("--db-name",type=str)
    parser.add_argument("--file-name",type=str)
    parser.add_argument("--templates",nargs="+",type=int)
    parser.add_argument("--orgs",nargs="+",type=str)
    parser.add_argument("--year-format",type=str)
    parser.add_argument("--target",type=int)
    parser.add_argument("--source-name",type=str)
    if DEBUG:
        # 設定在config裡
        analysis_type = DEFAULT_ANALYSIS_TYPE #AnalysisItemType.PaperPresidentReportESI
            
        model_id = DEFAULT_MODEL_ID # 1
        main_version = DEFAULT_MAIN_VER # "2026-03-12" 
        compare_version = DEFAULT_COMP_VER # "2025-03-13"
        output_path = DEFAULT_OUTPUT_PATH # "../PRIS_OUTPUT//"

        db_name = DEFAULT_DB_NAME 
        file_name = DEFAULT_FILE_NAME
        template_types = DEFAULT_TEMPLATE_TYPES
        org_ids = DEFAULT_ORG_IDS
        year_list = DEFAULT_YEAR_LIST
        year_format = DEFAULT_YEAR_FORMAT
        target = DEFAULT_TARGET
        source_name = DEFAULT_SOURCE_NAME
        output_path = DEFAULT_OUTPUT_PATH
        
    else:
        if len(sys.argv) == 1:
            rprint(f"[red]非DEBUG ENV，請輸入參數[/red]")
            return
        
        args = parser.parse_args()
        analysis_type = args.analysis_type
        output_path = args.output_path
        if analysis_type == 6:
            model_id = args.model_id
            main_version = args.main_version
            compare_version = args.compare_version
        elif analysis_type == 4:
            db_name = args.db_name
            file_name = args.file_name
            template_types = args.templates
            org_ids = args.orgs
            year_list = args.years
            year_format = args.year_format
            target = args.target
            source_name = args.source_name


    params = {"analysis_type" : analysis_type,"output_path" : output_path}
    if analysis_type == 6:
        params.update({
            "model_id" : model_id,
            "main_version" : main_version,
            "compare_version" : compare_version,
        })
    elif analysis_type == 4:
        params.update({
            "db_name":db_name,
            "file_name": file_name,
            "template_types" :template_types,
            "org_ids" : org_ids,
            "year_list" : year_list,
            "target" : target,
            "year_format": year_format,
            "source_name": source_name
        })


    try:
        #export_file_path = run_report(analysis_type= analysis_type, model_id= model_id, main_version=main_version, compare_version=compare_version, output_path= output_path)
        export_file_path = run_report(**params)
        rprint(f"[green] {export_file_path} 匯出完成!! [/green]")
    except PRISError as e:
        rprint(f"[red]{e}[/red]")


if __name__ == "__main__":
    main()
