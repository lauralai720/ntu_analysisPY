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

#config
from config import *


# PRIS
from pris import run_report
from exceptions import PRISError
from analysis.analysis_type import AnalysisItemType


def main():

    parser = argparse.ArgumentParser(description="報表匯出工具")
    parser.add_argument("--analysis-type", default = "6", help="分析項目，校長報表(ESI)- 6")
    parser.add_argument("--model-id", required=True, help="模組ID，國內研究型大學- 1, 台大與亞太鄰近大學- 2")
    parser.add_argument("--main-version", required=True, help="主要版本，格式 yyyy-MM-dd")
    parser.add_argument("--compare-version", required=True, help="比較版本，格式 yyyy-MM-dd")
    parser.add_argument("--output", default="../PRIS_OUTPUT//", help="輸出檔案路徑")


    if DEBUG:
        analysis_type = AnalysisItemType(DEFAULT_ANALYSIS_TYPE) #AnalysisItemType.PaperPresidentReportESI
        model_id = DEFAULT_MODEL_ID # 1
        main_version = DEFAULT_MAIN_VER # "2026-03-12" 
        comp_version = DEFAULT_COMP_VER # "2025-03-13"
        output_path = DEFAULT_OUTPUT_PATH # "../PRIS_OUTPUT//"
    else:
        args = parser.parse_args()
        analysis_type = AnalysisItemType(int(args.analysis_type))
        model_id = int(args.model_id)
        main_version = args.main_version
        comp_version = args.compare_version
        output_path = args.output

    try:
        run_report(analysis_type= analysis_type, model_id= model_id, main_version=main_version, comp_version=comp_version, output_path= output_path)
    except PRISError as e:
        rprint(f"[red]{e}[/red]")

if __name__ == "__main__":
    main()
