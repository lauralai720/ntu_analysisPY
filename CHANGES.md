# PRISToPy 優化版變更清單

驗證方式與結果見 tests/ (SQLite 替身 + pandas 對照;**未連線 SQL Server 實測**)。
標 [需對照 C#] 者是我判斷為 bug、但無法用原始 C# 驗證的項目。

## A. 暫存表 insert 效能 (問題 3)
| 檔案 | 變更 |
|---|---|
| database/table.py | 新增 `ExtraColumnTable.insert_temp_table_by_patterns`:N 個機構改為「(key,pattern) VALUES 清單 JOIN 來源表」,每批 300 個只掃描一次 |
| database/subject.py | 新增 `Subject.add_by_patterns / drop_temp_table / create_index`;暫存表編號改為建構時領取(修同名衝突) |
| components/subject_info.py | WOS 機構:先在 Python 收集 (key,pattern) 再批次寫入;ESI 機構:迴圈 `Add` → `AddRange` |
| analysis/president_wos_analysis.py | 「第一/通訊作者」暫存表只建一次(S2、S3 共用,原本重建 2 次) |
| database/sql.py | 移除每次 SQL 前的 `SELECT 1`(改為閒置 60 秒才 ping)、cursor 一律關閉、`do_no_query(commit=False)`、`transaction()`、暫存表登錄與結束清除 |
| database/bind.py | 欄位型別查詢:不再每次 `connect()` 新連線(且從未關閉);改既有連線 + 參數化 + 快取 |
| pris.py | `run_report` finally 清除暫存表 |

## B. Bug 修正
- table.py / join_table.py:年份區間 INSERT 傳入 list(`[f"..."]`)→ `cursor.execute` TypeError;`YJoinTable.add_label_col` 簽名錯誤且呼叫不存在的方法;Table 複製建構子 `outer` 判斷永遠為 False;`_set_collate` 屬性名稱錯誤被 except 吞掉(修正後預設仍關閉,維持現有輸出)
- year_selector.py:`raise("字串")` → `raise PRISError`
- metrics.py:`Indicator.avg_cited` 的 `if not df` → `is None`;`div_data_tables` percent 分支(iterrows 賦值無效)無作用;`binary_search_find_rank` 空清單
- data_analysis.py:`b06_h_index_calculate` 呼叫參數錯誤必定 TypeError(重寫);`compare_to_previous_years` 補 TypeError、先判斷再算前一年
- president_wos_analysis.py:S9「*」列使用殘留的 org_key [需對照 C#];`sum` 蓋掉內建且遇缺年份 TypeError
- util.py:`convert_type` 把 "nan"/"inf"/"1_000" 轉成數字
- report_exporter.py:裸 `except` 改為 PermissionError / OSError
- pris.py:無法到達的程式碼、`dal` 未宣告、年份空清單
- requirements.txt:改 UTF-8、加入 pyarrow、移除 pythonnet / clr_loader / cffi / pycparser

## C. 效能(純 pandas)
- data_analysis.a02_sumup_calculate:iterrows + loc 逐列新增 → groupby(30,000 列 2.0s → 0.013s,輸出含 dtype 相同)
- data_analysis.a08_cntavg_calculate:apply(axis=1) → 向量運算

## D. 刻意「沒有」修改、但建議你確認的項目
見審查報告(insert_integrate_data 的別名遮蔽、ComputeObject.query 的 bind 欄位、get_rank 的 select_field_name、
Subject 無 DROP、Encrypt/TrustServerCertificate 等)。
