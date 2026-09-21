```
py --version 
Python 3.11.9
```

**使用方式**</br>
from pris import run_report </br>
run_report(**kwargs):</br>
呼叫參數請看底下的參數說明

main.py測試用的呼叫方式</br>
python main.py --model-id 2 --main-version 2026-03-12 --compare-version 2025-03-13</br>
```
-- 若要使用main測試，請記得環境設定成prod
-- $env:APP_ENV="prod"
```

**參數說明**
- 校長報表(ESI)
    example : kwargs = {"analysis_type" = 6, "model_id" = 1, "main_version" = "2026-03-12", "compare_version"="2025-03-13", "output_path"="XXXX"}</br>
    * analysis_type - 分析項目
        - 1 - 
        - 2 - 
        - 3 - 
        - 4 - 
        - 5 - 
        - 6 - 校長報表(ESI)

    * model_id - 模組
        - 6 - 校長報表(ESI)
            - 1 - 國內研究型大學
            - 2 - 台大與亞太鄰近大學

    * main_version - 主要版本
        - 格式 : yyyy-mm-dd

    * compare_version - 比較版本
        - 格式 : yyyy-mm-dd

    * output_path - 匯出資料夾路徑