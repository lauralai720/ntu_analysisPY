import math
import pandas as pd
from typing import TypeVar, Callable

from config import *

T = TypeVar("T")

def try_parse(value: object, target_type: Callable[[object], T], default: T) -> tuple[bool, T]:
    '''轉換型態'''
    try:
        return True, target_type(value)
    except (ValueError, TypeError):
        return False, default


def str_to_title(s: str) -> str:
    '''將字串轉成第一個自字母大寫(先轉全小寫在title化)'''
    return s.lower().title()


## 因為如果值是數字，用string方式寫入excel欄位，excel會跳警告(是數字還是文字)
## 所以如果是數字要先轉換才不會有警告
def convert_type(text_value):
    '''
    將數字字串轉成純數字(int、float)
    因為如果值是數字，用string方式寫入excel欄位，excel會跳警告(是數字還是文字)
    '''
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
        value = float(text_value)
        # [Bug fix] float() 也接受 "nan" / "inf" / "1_000" 這類字串,寫進 Excel 會變成無效值或改變原文
        if not math.isfinite(value) or "_" in text_value:
            return text_value
        return value
    except ValueError:
        # 轉換失敗代表是純文字 (例如 "text")，直接回傳原字串
        return text_value

def get_per_year_list(from_y:int, to_y:int) -> list[int]:
    '''
    有頭尾的年份，回傳逐年年份列表
    例: 2018-2021 => [2018,2019,2020,2021]
    '''
    return list(range(from_y, to_y + 1))


def get_year_range_list(year_list:list[str] = None, min_y : int = 0, max_y :int = 0, year_range:int = YEAR_RANGE, format:int = 1) -> list[str]:
    '''
    可以輸入年份列表([2000,2001,2002...])或最小年跟最大年
    year_range為年份區間，例如year_range=3，區間為 2000-2002
    format = 1 逐年，2000-2002、2001-2003...
    format = 2 連接上一個結束年，2000-2002、2003-2005...[目前沒用到，保留彈性]
    '''
    if year_list:
        int_years = [int(x) for x in year_list]
        min_y = min(int_years)
        max_y = max(int_years)

    start_y= min_y
    stop_y = max_y
    select_years = []

    while (start_y + year_range - 1 ) <= stop_y:
        end_y = start_y + year_range - 1
        select_years.append(f"{start_y}-{end_y}")
        start_y = start_y+1 if format == 1 else end_y+1

    return select_years


num_ch_list = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
def get_num_ch(i) -> str:
    '''
    輸入數字(1-99)，將數字轉國字數字字串
    '''
    if (i <=0 or i >= 100):
        return "N"
    ret = ""
    if (i>9):
        if (i<20):
            ret += "十"
        else:
            ret += f"{num_ch_list[(i // 10) - 1]}十"

    if (i % 10 != 0):
        ret += f"{num_ch_list[(i % 10) - 1]}"

    return ret

def org_serial_code_type(org_serial:str):
    '''
    輸入OrgSerial，按照級別，把OrgSerial用成集合狀態，主要用在sql like 語法
    '''
    if org_serial[9:11] == "00":
        return org_serial[:9] + "%"
    if org_serial[11:13] == "00":
        return org_serial[:11] + "%"
    if org_serial[13:15] == "00":
        return org_serial[:13] + "%"
    return org_serial

def join_dataframes(df1, df2):
    '''
    將兩個DataFrame做merge
    兩個DataFrame的資料結構必須一樣，只有最後一個colum的值是不一樣的
    key_col_num代表前面有幾個欄位是要當key判斷
    如果key_col_num=2代表前兩個欄位的值必須一樣才能合併在同一列
    '''
    # 取得共同欄位
    common_cols = list(set(df1.columns) & set(df2.columns))
    # outer join
    result = pd.merge(df1, df2, on=common_cols, how='outer', suffixes=('', '_dup'))
    # 如果要移除重複欄位，可進一步處理
    # result = result.loc[:,~result.columns.str.endswith('_dup')]
    return result


def join_diff_dataframes(df1, df2, key_col_num:int)->pd.DataFrame:
    '''
    將兩個不同欄位名稱的DataFrame做merge，key_col_num需替換成相同欄位名稱的數量，如果key_col_num=2 代表 前兩欄的欄位名稱會被替換成M1、M2<br>
    新的dataframe是替換名稱欄+最後一欄，之後丟給join_dataframes做合併
    '''
    key_cols = [f'M{i+1}' for i in range(key_col_num)]

    df1_new = df1.iloc[:, list(range(key_col_num)) + [-1]].copy()
    df2_new = df2.iloc[:, list(range(key_col_num)) + [-1]].copy()
    # 1. rename column key
    df1_new.columns = key_cols + ['Column1']
    df2_new.columns = key_cols + ['Column2']

    # 2. 將兩個df merge
    df_merged = join_dataframes(df1_new, df2_new)

    return df_merged


def get_ratio(a, b) -> str:
    '''
    比率，部分量(b) 占 總體量(a) 的關係
    固定顯示小數點後 16 位
    '''
    a_res, a_f = try_parse(a, float, 0.0) #try_parse_float(sum)
    b_res, b_f = try_parse(b, float, 0.0) #try_parse_float(val)
    if a_res and b_res and a_f:
        rat = b_f/a_f
        rat = f"{rat:.16f}"
        return rat
    return ""


def get_growth_rate(pre_val, cur_val, use_percentage:bool = False, default_na:str = "", ndigits:int=16) -> str:
    '''
    成長率，(目前的值cur_val-前一個值pre_val)/前一個值pre_val<br>
    use_percentage = True 回傳成百分比(*100) ; default_na 設定N/A時defualt回傳值 ; ndigits 四捨五入到小數點第X位，預設16<br>
    '''
    pp_res, pre_f = try_parse(pre_val, float, 0.0) #try_parse_float(pre_val)
    cp_res, cur_f = try_parse(cur_val, float, 0.0) #try_parse_float(cur_val)

    if pp_res and cp_res and cur_f:
        rat =  round((cur_f - pre_f) / pre_f, ndigits)
        if use_percentage:
            rat *= 100
        return rat
    return default_na