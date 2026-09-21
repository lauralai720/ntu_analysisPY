import pandas as pd

# PRISUtilityKit.DBAL.Lib.Utils.Delimiter
DELIMITER = "\x1c"

class DataTableFormatter:
    def __init__(self,s1_h:str,s2_h:str,y_h:str,ex_list:list[str] = None):
        #self.set_data: set[tuple[str, ...]] = set()
        self.set_data_dict = {} # 因為python的set基本上會打亂，先改用dict存，讓出來的結果跟C#一樣
        self.table:list[tuple[dict[tuple[str, ...], str], str, str]] = []
        self.extenion: list[str] = ex_list
        self.s1_header: str = s1_h
        self.s2_header: str = s2_h
        self.year_header: str = y_h

    def add(self, df:pd.DataFrame, default_val:str = "0"):
        
        last_column_name = df.columns[-1]

        key_list = df.apply(lambda row: self.get_str_array(row, self.s1_header, self.s2_header,self.year_header, self.extenion),axis=1).to_list()

        # 3. 提取最後一欄的所有數值
        values = df[last_column_name].astype(str)

        self.set_data_dict.update(dict.fromkeys(key_list))

        # 5. 用 zip 打包成當前表格的字典
        current_dict = dict(zip(key_list, values))
        self.table.append((current_dict, df.table_name, default_val))

        # str_dict: dict[tuple[str, ...], str] = {}
        # for _,row in df.iterrows():
        #     k = self.get_str_array(row, self.s1_header, self.s2_header,self.year_header, self.extenion)
        #     self.set_data_dict[k] = True
        #     str_dict[k] = str(row.iloc[len(df.columns)-1])

        # self.table.append((str_dict, df.table_name, default_val))

    def create_data_frame(self, set_data_keys, s1: str, s2: str, s3: str, extension: list[str]) -> pd.DataFrame:
        # 1. 動態組合出所有的欄位名稱 (Headers)
        headers = []
        if s1 is not None: headers.append(s1)
        if s2 is not None: headers.append(s2)
        if s3 is not None: headers.append(s3)
        if extension is not None: headers.extend(extension)
        
        # 2. 將集合轉成二維 List。
        # 因為 Python 的 DataFrame 可以直接吃這種結構，完全不需要手動一筆一筆建立 Row
        matrix_data = [list(item) for item in set_data_keys]
        
        # 3. 一行建立 DataFrame
        df = pd.DataFrame(matrix_data, columns=headers)
        return df

    def convert_dict_to_data_frame(
        self,
        df: pd.DataFrame, 
        inner_dict: dict[tuple[str, ...], str], 
        column_name: str, 
        s1: str, s2: str, s3: str, 
        suffix: str, 
        default_val: str, 
        extension: list[str]
    ) -> None:
        
        # 1. 決定要拿哪幾個欄位來當作比對的 Key (等同於 C# 的 getStringArray 邏輯)
        key_columns = []
        if s1 is not None: key_columns.append(s1)
        if s2 is not None: key_columns.append(s2)
        if s3 is not None: key_columns.append(s3)
        if extension is not None: key_columns.extend(extension)
        
        # 2. 定義防呆回傳值 (等同於 $"{defaultVal}{suffix}")
        fallback_val = f"{default_val}{suffix}"
        
        # 3. 核心行：將指定的欄位組合轉成 tuple，並直接去 dict 撈資料
        #    (axis=1 代表按列處理。tuple(row) 會把那一列選定欄位的值打包成不可變的 tuple，與字典對齊)
        df[column_name] = df.apply(
            lambda row: inner_dict.get(
                self.get_str_array(row, self.s1_header, self.s2_header, self.year_header, self.extenion),
                fallback_val
            ),
            axis=1
        )
    ## 原C# function 是回傳 DataTable
    def get_data_frame(self, suffix: str = None) -> pd.DataFrame:
        # 1. 呼叫上面的優化函式，建立初始的 DataFrame
        df = self.create_data_frame(self.set_data_dict.keys(), self.s1_header, self.s2_header, self.year_header, self.extenion)
        
        # 2. 處理 suffix 的預設值 (等同於 suffix = suffix ?? "")
        if suffix is None:
            suffix = ""
            
        # 3. 遍歷那串複雜的 tables 結構
        #    item.Item1 -> inner_dict
        #    item.Item2 -> col_name
        #    item.Item3 -> status_or_whatever (對應你 C# 傳入 convertDictToDataTable 的倒數第二個參數)
        for inner_dict, col_name, extra_param in self.table:
            # 呼叫你原本對應的 convertDictToDataTable 邏輯
            # 注意：在 Python 中，物件是以「傳址」傳遞，所以功能會在 convert 函式內部直接修改 df
            self.convert_dict_to_data_frame(
                df, inner_dict, col_name, 
                self.s1_header, self.s2_header, self.year_header, 
                suffix, extra_param, self.extenion
            )
            
        return df
    
    # 照原本function命名
    def get_str_array(self, row:pd.Series, subj1, subj2, subj3, extension: list[str]):
        i = 0
        s1 :str = None
        s2 :str = None
        s3 :str = None

        if subj1 is not None:
            s1 = str(row.iloc[i])
            i += 1
        if subj2 is not None:
            s2 = str(row.iloc[i])
            i += 1
        if subj3 is not None:
            s3 = str(row.iloc[i])
            i += 1

        ex :list[str] = None
        if extension is not None:
            ex =[]
            for j in range(len(extension)):
                ex.append(str(row.iloc[i+j]))

        tmp = [s1, s2, s3]

        if ex is not None:
            tmp += ex

        return tuple(tmp)


## 因為如果值是數字，用string方式寫入excel欄位，excel會跳警告(是數字還是文字)
## 所以如果是數字要先轉換才不會有警告
@staticmethod
def convert_type(text_value):
    # 若為空值或 None 直接回傳
    if not text_value:
        return text_value

    if not isinstance(text_value, str):
        return text_value
           
    # 去除前後空白
    text_value = text_value.strip()
    
    try:
        # 嘗試轉換成整數 (例如 "19")
        if text_value.isdigit() or (text_value.startswith('-') and text_value[1:].isdigit()):
            return int(text_value)
            
        # 嘗試轉換成浮點數 (例如 "19.5")
        return float(text_value)
    except ValueError:
        # 轉換失敗代表是純文字 (例如 "text")，直接回傳原字串
        return text_value

@staticmethod
def get_year_range_list(year_list:list[str] = None, min_y : int = 0, max_y :int = 0) -> list[str]:
    if year_list:
        int_years = [int(x) for x in year_list]
        min_y = min(int_years)
        max_y = max(int_years)

    start_y= min_y
    stop_y = max_y
    select_years = []

    while (start_y + 2) <= stop_y:
        end_y = start_y + 3 - 1
        select_years.append(f"{start_y}-{end_y}")
        start_y = start_y+1

    return select_years
