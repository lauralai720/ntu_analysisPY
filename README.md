```
py --version 
Python 3.11.9
```

**使用方式**</br>
from pris import run_report </br>
run_report(analysis_type: int, model_id:int, main_version: str, comp_version: str, output_path: str = "./output//"):</br>

main.py測試用的呼叫方式</br>
python main.py --model-id 2 --main-version 2026-03-12 --compare-version 2025-03-13</br>

**參數說明**
1. analysis_type - 分析項目
    - 1 - 
    - 2 - 
    - 3 - 
    - 4 - 
    - 5 - 
    - 6 - 校長報表(ESI)

2. model_id - 模組
    - 6 - 校長報表(ESI)
        - 1 - 國內研究型大學
        - 2 - 台大與亞太鄰近大學

3. main_version - 主要版本
    - 格式 : yyyy-mm-dd

4. comp_version - 比較版本
    - 格式 : yyyy-mm-dd

5. output_path - 匯出資料夾路徑