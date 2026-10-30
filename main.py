
import os
print(f"================> MY PYTHON PID: {os.getpid()}")

from rich import print as rprint
import argparse
import sys


#config
from config import *

# PRIS
import common.util as Util
from pris import run_report
from exceptions import PRISError


def main():
    parser = argparse.ArgumentParser(description="報表匯出工具")
    parser.add_argument("--analysis-type", required=True, default = 6,type=int, help="分析項目，校長報表(WOS)- 4 / 校長報表(ESI)- 6")
    parser.add_argument("--file-name",type=str,help="專案名稱、檔名用")
    parser.add_argument("--template-types",nargs="+",type=int,help="報表類型")
    parser.add_argument("--org-ids",nargs="+",type=str,help="機構")
    parser.add_argument("--fields",nargs="+",type=int,help="領域")
    parser.add_argument("--year-list",nargs="+",type=str,help="分析年份，ESI 格式:yyyy-mm-dd，要有兩組以上/ WOS格式:yyyy yyyy yyyy")
    parser.add_argument("--output-path", required=True, default="../PRIS_OUTPUT//", help="輸出檔案路徑")
    parser.add_argument("--db-name",type=str)
    parser.add_argument("--year-format",type=str)
    parser.add_argument("--target",type=int)
    parser.add_argument("--source-name",type=str)
    parser.add_argument("--if-val-1",type=int,help="[WOS][選填]高影響期刊係數指數1，1~100")
    parser.add_argument("--if-val-2",type=int,help="[WOS][選填]高影響期刊係數指數2，1~100")
    parser.add_argument("--range-year",type=int,help="[WOS][選填]N年論文成長率的[N]，2~10")
    parser.add_argument("--top-n",type=int,help="[ESI][選填]各領域前N名的機構，3~10")

    params = {}
    if DEBUG:
        analysis_type = DEFAULT_ANALYSIS_TYPE #AnalysisItemType.PaperPresidentReportESI
        # 設定在config裡
        params = {
            "analysis_type" : analysis_type,
            "output_path" : DEFAULT_OUTPUT_PATH,
        }

        if analysis_type == 6:
            params.update({
                "file_name": DEFAULT_ESI_PN,
                "template_types" :DEFAULT_ESI_TEMPLATE_TYPES,
                "org_ids" : DEFAULT_ESI_ORG_IDS,
                "year_list" : DEFAULT_ESI_YEAR_LIST,
                "fields": DEFAULT_ESI_FIELD_IDS,
                # 以下選填，不需要可以註解掉
                "top_n" : DEFAULT_ESI_TOP_N,
            })


        elif analysis_type == 4:
            params.update({
                "file_name": DEFAULT_FILE_NAME,
                "db_name" : DEFAULT_DB_NAME,
                "template_types" :DEFAULT_TEMPLATE_TYPES,
                "org_ids" : DEFAULT_ORG_IDS,
                "year_list" : list(map(str,Util.get_per_year_list(DEFAULT_FROM_YEAR, DEFAULT_TO_YEAR))),
                "target" : DEFAULT_TARGET,
                "year_format": DEFAULT_YEAR_FORMAT,
                "source_name": DEFAULT_SOURCE_NAME,
                # 以下選填，不需要可以註解掉
                # "if_val_1" : DEFAULT_IF_1,
                # "if_val_2" : DEFAULT_IF_2,
                # "range_year" : DEFAULT_YEAR_RANGE,
            })

    else:
        if len(sys.argv) == 1:
            rprint(f"[red]非DEBUG ENV，請輸入參數[/red]")
            return
        args = parser.parse_args()
        params = args


    try:
        export_file_path = run_report(**params)
        rprint(f"[green] {export_file_path} 匯出完成!! [/green]")
    except PRISError as e:
        rprint(f"[red]{e}[/red]")


if __name__ == "__main__":
    main()
