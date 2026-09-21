# config.py
import os

ENV = os.environ.get("APP_ENV", "dev")  # 預設是 dev,可以透過環境變數改成 prod

ESI_FIELD_SORT =  ["工學","生命科學","社科","理學","農學","醫學","跨領域"]

WOS_ORGS = ["TWU000001","TWU000091","TWU000013","TWU000002","TWU000003","TWU000007","TWU000006"]

YEAR_RANGE = 3

if ENV == "dev":
    DEBUG=True
    DEFAULT_DB_IP="140.112.180.160"
    DEFAULT_DB_USER="Lis_User"
    DEFAULT_DB_PW="5566server^.<"

    DEFAULT_ANALYSIS_TYPE=4
    DEFAULT_MODEL_ID=2
    DEFAULT_MAIN_VER="2026-03-12"
    DEFAULT_COMP_VER="2025-03-13"
    DEFAULT_OUTPUT_PATH="../PRIS_OUTPUT//"

elif ENV == "prod":
    DEBUG=False
    DEFAULT_DB_IP="140.112.180.160"
    DEFAULT_DB_USER="Lis_User"
    DEFAULT_DB_PW="5566server^.<"
else:
    raise ValueError(f"未知的環境:{ENV}")