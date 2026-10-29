
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
    parser.add_argument("--templates",nargs="+",type=int,help="報表類型")
    parser.add_argument("--orgs",nargs="+",type=str,help="機構")
    parser.add_argument("--fields",nargs="+",type=int,help="領域")
    parser.add_argument("--years",nargs="+",type=str,help="分析年份，ESI 格式:yyyy-mm-dd，要有兩組以上/ WOS格式:yyyy yyyy yyyy")
    parser.add_argument("--output-path", required=True, default="../PRIS_OUTPUT//", help="輸出檔案路徑")
    parser.add_argument("--db-name",type=str)
    parser.add_argument("--year-format",type=str)
    parser.add_argument("--target",type=int)
    parser.add_argument("--source-name",type=str)
    parser.add_argument("--if-val-1",type=int, default="15", help="高影響期刊係數指數1，1~100，預設 15")
    parser.add_argument("--if-val-2",type=int, default="30", help="高影響期刊係數指數1，1~100，預設 30")
    parser.add_argument("--range-year",type=int, default="3", help="N年論文成長率的[N]")

    if DEBUG:
        # 設定在config裡
        analysis_type = DEFAULT_ANALYSIS_TYPE #AnalysisItemType.PaperPresidentReportESI
        output_path = DEFAULT_OUTPUT_PATH # "../PRIS_OUTPUT//"
        
        if analysis_type == 6:
            template_types = DEFAULT_ESI_TEMPLATE_TYPES
            org_ids = DEFAULT_ESI_ORG_IDS
            year_list = DEFAULT_ESI_YEAR_LIST
            field_ids = DEFAULT_ESI_FIELD_IDS
            file_name = DEFAULT_ESI_PN

        elif analysis_type == 4:
            file_name = DEFAULT_FILE_NAME
            db_name = DEFAULT_DB_NAME 
            template_types = DEFAULT_TEMPLATE_TYPES
            org_ids = DEFAULT_ORG_IDS
            year_list = list(map(str,Util.get_per_year_list(DEFAULT_FROM_YEAR, DEFAULT_TO_YEAR)))
            year_format = DEFAULT_YEAR_FORMAT
            target = DEFAULT_TARGET
            source_name = DEFAULT_SOURCE_NAME

    else:
        if len(sys.argv) == 1:
            rprint(f"[red]非DEBUG ENV，請輸入參數[/red]")
            return
        
        args = parser.parse_args()
        analysis_type = args.analysis_type
        output_path = args.output_path
        file_name = args.file_name
        template_types = args.templates
        org_ids = args.orgs
        year_list = args.years
        
        if analysis_type == 6:
            field_ids = args.fields
        
        elif analysis_type == 4:
            db_name = args.db_name
            year_format = args.year_format
            target = args.target
            source_name = args.source_name

    params = {
        "analysis_type" : analysis_type,
        "output_path" : output_path,
        "file_name": file_name,
        "template_types" :template_types,
        "org_ids" : org_ids,
        "year_list" : year_list,
    }
    if analysis_type == 6:
        params.update({
            "field_ids": field_ids,
        })
    
    elif analysis_type == 4:
        params.update({
            "db_name":db_name,
            "target" : target,
            "year_format": year_format,
            "source_name": source_name
        })
        if DEBUG:
            params.update({
                "jcr_if_1": DEFAULT_IF_1,
                "jcr_if_2": DEFAULT_IF_2,
                "range_year" : DEFAULT_YEAR_RANGE
            })
        else:
            if args.if_val_1 is not None:
                params['jcr_if_1'] = args.if_val_1
            if args.if_val_2 is not None:
                params['jcr_if_2'] = args.if_val_2
            if args.range_year is not None:
                params['range_year'] = args.range_year

    try:
        export_file_path = run_report(**params)
        rprint(f"[green] {export_file_path} 匯出完成!! [/green]")
    except PRISError as e:
        rprint(f"[red]{e}[/red]")

if __name__ == "__main__":
    main()
