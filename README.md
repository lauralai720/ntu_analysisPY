```
py --version 
Python 3.11.9
```

**使用方式**</br>
from pris import run_report </br>
run_report(**kwargs):</br>
</br>
呼叫參數請看底下的參數說明
</br>


**參數說明**
- 通用參數
    * analysis_type - 分析項目
        - 1 - 
        - 2 - 
        - 3 - 
        - 4 - 校長報表(WOS)
        - 5 - 
        - 6 - 校長報表(ESI)
        
    * output_path - 匯出資料夾路徑

- 校長報表(ESI)</br>
    example : </br>
        kwargs = {</br>
            "analysis_type" = 6, </br>
            "output_path"="XXXX", </br>
            "model_id" = 1, </br>
            "main_version" = "2026-03-12", </br>
            "compare_version"="2025-03-13"</br>
        }</br>

    * model_id - 模組，int
        - 6 - 校長報表(ESI)
            - 1 - 國內研究型大學
            - 2 - 台大與亞太鄰近大學

    * main_version - 主要版本，str
        - 格式 : yyyy-mm-dd

    * compare_version - 比較版本，str
        - 格式 : yyyy-mm-dd


- 校長報表(WOS)</br>
    example : </br>
        kwargs = {</br>
            "analysis_type"=4, </br>
            "output_path"="XXXX", </br>
            "db_name":"PRIS_WOS_校長報表_202604_2015_2025_260423",</br>
            "file_name": "台大院系級",</br>
            "template_types":[102,103],</br>
            "org_ids" : ["TWU000001","TWU000091","TWU000013","TWU000002","TWU000003","TWU000007"],</br>
            "year_list" : ["2020", "2021","2022","2023","2024", "2025"],</br>
            "target" : 2,</br>
            "year_format": "x-y年",</br>
            "source_name": "SCI-E、SSCI、A&HCI"</br>
        }</br>

    * db_name - 要抓取的DB名稱，str

    * file_name - 輸出的檔名，str
        - 原pris的預設檔名: 國內七所研究型大學 / 台大院級 / 台大系所 / 國內十七所大學/ 亞太代表性大學

    * template_types - 報表類型列表，list[int]，格式 : [101,102...,109]
        - 101 => S1 - 歷年上半年論文數統計
        - 102 => S2 - 論文數統計
        - 103 => S3 - 被引次數統計
        - 104 => S4 - 論文成長率
        - 105 => S5 - 平均被引用次數統計
        - 106 => S6 - 論文數及成長率
        - 107 => S7 - 高影響期刊係數前15%及40%論文數
        - 109 => S9 - 三年論文成長率
    
    * org_ids - 機構列表，list[str]，格式 : ["TWU000001","TWU000091","TWU000013"]
        - 如果要台大的院系資料，請傳送台大機構編號就好 => ["TWU000001"]
    
    * year_list - 年份列表，list[str]，格式: ["2020", "2021","2022","2023","2024", "2025"]
        - 三年的部分會由程式內部自行組成 ["2020-2022","2021-2023"...]，無須帶入
    
    * target - 報表表格標題之一，表格標題顯示用，會對應相對應的字串，int，
        - 1 - "國內{0}所研究型大學"
        - 2 - "臺灣大學各學院"
        - 3 - "臺灣大學x各學院系所"
        - 4 - "國內{0}所大學"
        - 5 - "亞太代表性大學"

    * year_format - 報表表格標題之一，表格標題顯示用，str
        - "x-y年" / "x歷年上半年-y歷年上半年"
    
    * source_name - 報表表格標題之一，表格標題顯示用，str
        - "SCI-E、SSCI、A&HCI" / "SCI-E" / "SSCI" / "A&HCI"

</br>
</br>

**main.py測試用的呼叫方式**</br>

*ESI報表*</br>
python main.py --analysis-type 6 --output-path "../PRIS_OUTPUT//" --model-id 2 --main-version 2026-03-12 --compare-version 2025-03-13</br>
</br>

*WOS報表*</br>
python main.py --analysis-type 4 --output-path "../PRIS_OUTPUT//" --target 1 --db-name "PRIS_WOS_校長報表_202604_2015_2025_260423" --file-name "國內研究型大學" --templates 102 103 104 105 109 --years 2020 2021 2022 2023 2024 2025 --orgs "TWU000001" "TWU000091" "TWU000013" "TWU000002" "TWU000003" "TWU000007" "TWU000006" --year-format "x-y年" --source-name "SCI-E、SSCI、A&HCI"</br>


```
-- 若要使用main測試，請記得環境設定成prod
-- $env:APP_ENV="prod"
```
</br>