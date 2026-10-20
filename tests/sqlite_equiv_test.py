"""
用 SQLite 當替身,實際執行「原版」與「優化版」所產生的 SQL,比對暫存表內容。
用法: python sqlite_equiv_test.py <專案根目錄> <輸出json>
(T-SQL → SQLite 只做最小必要的語法轉換;重點是驗證 *集合運算的語意* 是否一致)
"""
import sys, os, re, json, random, sqlite3, time
root, outjson = sys.argv[1], sys.argv[2]
sys.path.insert(0, root); sys.path.insert(0, os.path.dirname(__file__))   # root 優先,harness 的 config / mssql_python 殿後
sys.path.remove(os.path.dirname(__file__)); sys.path.append(os.path.dirname(__file__))

import database.sql as sqlmod
from database.sql import SQLExecute

# ---------------- 建測試資料 ----------------
random.seed(20260101)
con = sqlite3.connect(":memory:")
cur = con.cursor()
cur.executescript("""
CREATE TABLE WOS_ORG (ISI_ID TEXT, AddressIndex INT, OrgName TEXT, Country TEXT, Reprint INT);
CREATE TABLE WOS_ORG_2nd (ISI_ID TEXT, AddressIndex INT, OrgName TEXT, Country TEXT, Reprint INT);
CREATE TABLE WOS_AUTHOR_ORG_RELATION (ISI_ID TEXT, AuthorIndex INT, AddressIndex INT, Reprint INT);
""")
first_level = ["TWU000001", "TWU000002", "TWU000003", "TWU000007", "TWU000091"]
second_level = []
for dept in range(1, 41):              # 40 個二級
    for sub in range(0, 6):            # 每個 0~5 三級
        second_level.append(f"TWU0000{dept:02d}{sub:02d}{random.randint(0,9):02d}0")  # 15 碼
second_level = sorted(set(s[:15].ljust(15,'0') for s in second_level))
rows1, rows2, rowsA = [], [], []
for i in range(400):
    isi = f"WOS:{i:09d}"
    for addr in range(1, random.randint(2, 4)):
        rp = random.choice([0, 1])
        rows1.append((isi, addr, random.choice(first_level), "TW", rp))
        for _ in range(random.randint(1, 3)):
            rows2.append((isi, addr, random.choice(second_level), "TW", rp))
        for a in range(1, random.randint(2, 4)):
            rowsA.append((isi, a, addr, rp))
cur.executemany("INSERT INTO WOS_ORG VALUES (?,?,?,?,?)", rows1)
cur.executemany("INSERT INTO WOS_ORG_2nd VALUES (?,?,?,?,?)", rows2)
cur.executemany("INSERT INTO WOS_AUTHOR_ORG_RELATION VALUES (?,?,?,?)", rowsA)

# ---------------- T-SQL → SQLite 轉譯 ----------------
executed = []
def translate(sql: str) -> str:
    sql = re.sub(r"\[[^\]]+\]\.dbo\.\[([^\]]+)\]", r"\1", sql)
    sql = sql.replace("N'", "'")
    sql = sql.replace("#TEMPTBL", "TEMPTBL")
    m = re.match(r"SELECT TOP 0 (.*) INTO (\S+) FROM (.*)$", sql, re.S)
    if m:
        sql = f"CREATE TABLE {m.group(2)} AS SELECT {m.group(1)} FROM {m.group(3)} LIMIT 0"
    # (VALUES ...) AS K([k],[p])  →  (SELECT column1 AS [k], column2 AS [p] FROM (VALUES ...)) AS K
    sql = re.sub(r"\(VALUES (.*?)\) AS K\(\[k\],\[p\]\)",
                 lambda m: f"(SELECT column1 AS [k], column2 AS [p] FROM (VALUES {m.group(1)})) AS K", sql, flags=re.S)
    return sql

def fake_do_no_query(sql_cmd, *a, **k):
    executed.append(sql_cmd)
    con.execute(translate(sql_cmd))
SQLExecute.do_no_query = staticmethod(fake_do_no_query)
SQLExecute.commit = staticmethod(lambda: None)
for n in ("register_temp_table", "forget_temp_table"):
    if not hasattr(SQLExecute, n):          # 原版沒有這些方法 → 補空實作即可
        setattr(SQLExecute, n, staticmethod(lambda *_: None))
SQLExecute.query = staticmethod(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no DB")))

# ---------------- 呼叫「真正的」get_subject ----------------
import common.db_schema as db_schema
from components.subject_info import WOSPaperOrgSubjectInfo
from components.paper_org_value import PaperOrgSelectedValue, PaperOrgSelectItem, AuthorIndex
db_schema.schema = db_schema.WOSSchema(); db_schema.schema.set_DB_name("dbx")

def build_selected(n_second):
    sel = PaperOrgSelectedValue()
    for s in first_level:
        sel.add(PaperOrgSelectItem(s, "校", "U"))
    chosen2 = random.sample(second_level, n_second)
    for s in chosen2:
        sel.add(PaperOrgSelectItem(s, "院", "C"))                  # 12~15 碼完整碼
    # 二、三級的萬用字元寫法 + 逗號分隔多值
    for dept in range(1, 15):
        sel.add(PaperOrgSelectItem(f"TWU0000{dept:02d}%", "系", "D"))   # TWU000001% 這種 9~11 碼
    sel.add(PaperOrgSelectItem("TWU000001127%", "醫", "M"))
    # 合併設定: 某二級碼在不同年度區間要併入其他碼
    sel.merge_items = {
        "TWU000001127%": {"1900_2300": ["TWU0000012%", "TWU0000013%"], "2010_2015": ["TWU0000014%"]},
        "TWU000002%":    {"2000_2020": ["TWU000003%"]},
    }
    return sel

results = {}
for label, ai in [("NotLimited", AuthorIndex.NotLimited), ("FirstAuthor", AuthorIndex.FirstAuthor),
                  ("Reprint", AuthorIndex.Reprint), ("FirstOrReprint", AuthorIndex.FirstOrReprint)]:
    for n2 in (20, 60):
        # 每個情境用乾淨的暫存表編號
        for t in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE name LIKE 'TEMPTBL%'")]:
            con.execute(f"DROP TABLE {t}")
        executed.clear()
        random.seed(n2)                     # 兩個版本用同一組輸入
        sel = build_selected(n2)
        info = WOSPaperOrgSubjectInfo.__new__(WOSPaperOrgSubjectInfo)
        info.orgs_selected_list = ["x"]; info.order_orgs_selected_list = []
        t0 = time.perf_counter()
        subj, binds, _, _, _ = info.get_subject(sel, author_index=ai)
        dt = time.perf_counter() - t0
        tmp = subj.temp_table_name.replace("#", "")
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({tmp})")]
        col_order_sig = cols                                  # 記錄欄位順序,另外報告
        # 依「欄位名稱」正規化,避免 set 迭代順序(每次執行不同)造成假差異
        rows = sorted((tuple(sorted(zip(cols, map(str, r)))) for r in con.execute(f"SELECT * FROM {tmp}").fetchall()))
        results[f"{label}/n2={n2}"] = {
            "n_keys": len(subj.subj_vals),
            "subj_vals_head": subj.subj_vals[:8],
            "subj_vals_hash": hash(tuple(subj.subj_vals)) if False else __import__("hashlib").md5("|".join(subj.subj_vals).encode()).hexdigest(),
            "n_rows": len(rows),
            "col_order": col_order_sig,
            "rows_hash": __import__("hashlib").md5(repr(rows).encode()).hexdigest(),
            "n_sql_statements": len(executed),
            "py_seconds_incl_sqlite": round(dt, 3),
            "max_sql_len": max(len(x) for x in executed),
        }
json.dump(results, open(outjson, "w"), ensure_ascii=False, indent=1)
print("done", len(results))
