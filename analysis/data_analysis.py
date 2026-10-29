import pandas as pd

import common.util as Util

def is_subject_match(row, subjs):
    '''
    假設 subjs 是一個 list，row 是 pandas.Series
    若 subjs 任何一個為 None，或與 row 前 n 個欄位有不同則回傳 False
    '''
    for i, subj in enumerate(subjs):
        if subj != row.iloc[i]:
            return False
    return True

def copy_subject_value_to_row(row_list, subjs):
    for i, subj in enumerate(subjs):
        row_list[i] = subj

def copy_column_value_to_subject(row, subjs):
    for i in range(len(subjs)):
        subjs[i] = row.iloc[i]

def serialize_multi_string_to_single(subjs):
    # 這裡請根據你的實際序列化規則實作
    return '|'.join(str(s) for s in subjs)

def df_column_rename(df : pd.DataFrame, index:int, rename:str) -> pd.DataFrame:
    '''將df指定欄位位置的col改名'''
    value_col = df.columns[index]
    df_new = df.rename(columns={value_col: rename})
    return df_new

# A02_SumUp.Calculate
# [優化] 原本用 iterrows + `ret.loc[len(ret)] = ...` 逐筆累加(每次 loc 新增列都是 O(n) 的複製 → 整體 O(n^2)),
#        改為排序後 groupby 加總。輸出欄位、列順序、dtype 與原版一致(見 tests/test_data_analysis_equiv.py)。
def a02_sumup_calculate(df : pd.DataFrame) -> pd.DataFrame:
    '''
    原PRIS A02_SumUp.Calculate
    '''
    subj_num = df.shape[1] - 1
    columns_list = list(df.columns)
    columns_list[subj_num] = "Sum"

    group_cols = list(df.columns[:subj_num])
    work = df.sort_values(by=group_cols, ascending=[True]*(subj_num-1) + [False])
    value_col = df.columns[subj_num]
    # 原版是逐筆 int(...) 後相加,這裡同樣先轉整數(含「小數截斷」行為),再加總
    work = work.assign(**{value_col: work[value_col].astype("int64")})

    ret = (work.groupby(group_cols, sort=False, dropna=False, as_index=False)[value_col].sum())
    ret.columns = columns_list
    return ret.reset_index(drop=True)

# B22_Ranking.Calculate
def b22_ranking_calculate(df : pd.DataFrame, analysis_idx:int = 0) -> pd.DataFrame:
    '''
    原PRIS B22_Ranking.Calculate
    '''
    df_ret = df.copy()
    value_col = df_ret.columns[-1]
    df_ret[value_col] = pd.to_numeric(df_ret[value_col], errors='coerce')
    df_ret = df_ret.dropna(subset=[value_col])

    # 排序欄位
    if analysis_idx != -1:
        group_cols = [col for i, col in enumerate(df_ret.columns[:-1]) if i != analysis_idx]
    else:
        group_cols = []

    # 排序    
    sort_cols = group_cols + [value_col]
    ascending = [True] * len(group_cols) + [False]
    df_ret = df_ret.sort_values(by=sort_cols, ascending=ascending)

    # 排名
    if group_cols:
        df_ret['Rank'] = df_ret.groupby(group_cols)[value_col].rank(method='min', ascending=False).astype(int)
    else:
        df_ret['Rank'] = df_ret[value_col].rank(method='min', ascending=False).astype(int)

    return df_ret.reset_index(drop=True)


# A08_CntAvg.Calculate
# [優化] 原本 df.apply(axis=1) 逐列呼叫 python 函式;改為向量運算,規則不變:
#   無法轉數字 → 0;分母(columns[-1])為 0 → 0;否則 columns[-2] / columns[-1],decimals>=0 時四捨五入
def a08_cntavg_calculate( df : pd.DataFrame, decimals:int = -1) -> pd.DataFrame:
    '''
    原PRIS A08_CntAvg.Calculate
    '''
    ret = df.copy()
    denom_col = df.columns[-2]
    num_col = df.columns[-1]

    num = pd.to_numeric(df[num_col], errors="coerce").astype("float64")
    denom = pd.to_numeric(df[denom_col], errors="coerce").astype("float64")
    invalid = num.isna() & df[num_col].notna() | denom.isna() & df[denom_col].notna()
    with __import__("numpy").errstate(divide="ignore", invalid="ignore"):
        avg = denom / num
    if decimals >= 0:
        avg = avg.round(decimals)
    avg = avg.where(~((num == 0) | invalid), 0)
    ret['CntAvg'] = avg
    return ret

# A08_CntAvg.Calculate JOIN
def a08_cntavg_calculate_join(df_1 : pd.DataFrame,df_2 : pd.DataFrame, decimals:int = -1) -> pd.DataFrame:
    '''
    A08_CntAvg.Calculate 先join兩個dataframe
    '''
    join_df = Util.join_dataframes(df_1, df_2)
    df = a08_cntavg_calculate(join_df, decimals=decimals)
    return df


def compare_to_previous_years(df, year_col_idx, ori_year_list, pre_year_func, proc, na_val_notation=None):
    val_map = {}

    # 建立 key 對應 value 的 map
    for _, row in df.iterrows():
        subjs = row.iloc[:-1].tolist()
        key = serialize_multi_string_to_single(subjs)
        try:
            val = float(row.iloc[-1])
            val_map[key] = val
        except (ValueError, TypeError):      # [Bug fix] NULL(None)會丟 TypeError,原本只接 ValueError
            continue

    result_rows = []
    for _, row in df.iterrows():
        subjs = row.iloc[:-1].tolist()
        try:
            val = float(row.iloc[-1])
            is_val_available = True
        except (ValueError, TypeError):
            is_val_available = False
            val = None

        ysubj = subjs[year_col_idx]
        if ysubj not in ori_year_list:        # 先判斷再算前一年,避免對不相關的值呼叫 pre_year_func
            continue
        key_subjs = subjs.copy()
        key_subjs[year_col_idx] = pre_year_func(ysubj)
        key = serialize_multi_string_to_single(key_subjs)

        if is_val_available and key in val_map:
            pre_y_val = val_map[key]
            new_val = proc(pre_y_val, val)
        else:
            new_val = na_val_notation if na_val_notation is not None else "N/A"

        result_row = subjs + [new_val]
        result_rows.append(result_row)

    # 建立結果 DataFrame
    result_df = pd.DataFrame(result_rows, columns=df.columns)
    return result_df


def growth_rate_series(values: list, use_percentage: bool = False, na_val="") -> list:
    """依序計算一串數值的成長率:第一期沒有前期 → ""(空白);前期為 0 → na_val。"""
    return [""] + [Util.get_growth_rate(p, c, use_percentage=use_percentage, default_na=na_val, ndigits=4) for p, c in zip(values, values[1:])]


# GrowthRate.Calculate
def growth_rate_calculate(df : pd.DataFrame, year_col_idx:int, ori_years : list[str], per_year_func, use_percentage: bool = True, na_val_notation=None) -> pd.DataFrame:
    '''依年份對應數值來計算成長率'''
    na_val = na_val_notation if na_val_notation is not None else "N/A"

    def rate(pre_y_val, val):
        return Util.get_growth_rate(pre_y_val, val, use_percentage=use_percentage, default_na=na_val, ndigits=4)

    return compare_to_previous_years(df, year_col_idx, ori_years, per_year_func, rate, na_val_notation)




