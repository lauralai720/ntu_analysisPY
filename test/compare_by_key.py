#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比對兩個「列順序不同」的 Excel(例如 台大院系級)。

做法
----
1. 可見工作表:每一列以 A、B、C 三欄(機構編碼、機構名稱1、機構名稱2)當作 key 來配對,
   key 完全一致的才比對 D 欄之後的內容。
   - 一個機構占多列的工作表(例如「論文數及成長率」每機構 6 列、
     「高影響期刊...」每機構 3 列),只有區塊第一列有 A/B/C,
     後面的列會沿用該區塊的 key,並以「區塊內第幾列」來配對。
   - 公式會參照 _Rawdata 的列號,兩邊順序不同時列號當然不同,
     所以比對前先把「參照列號」換成「相對於本列的位移」再比。
2. _Rawdata 隱藏工作表:本身沒有 key,但第 n 列對應可見工作表的第 n+位移 列,
   所以透過可見工作表的 key 找到兩邊各自對應的列,再逐欄比數值。
3. 數值預設容許極小的浮點誤差(1e-9),可用 --exact 改成完全一致。

用法
----
    python compare_excel_by_key.py 檔案1.xlsx 檔案2.xlsx
    python compare_excel_by_key.py 檔案1.xlsx 檔案2.xlsx --out 比對結果.xlsx --tol 1e-9
    python compare_excel_by_key.py 檔案1.xlsx 檔案2.xlsx --exact
    python compare_excel_by_key.py 檔案1.xlsx 檔案2.xlsx --sheets 論文數統計 被引次數統計

結束代碼:0 = 全部一致,1 = 有差異。
"""
import argparse
import math
import re
import sys
from collections import Counter, defaultdict

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

RAW_SUFFIX = "_Rawdata"
KEY_COLS = (1, 2, 3)  # A、B、C
REF_RE = re.compile(r"'(?P<sheet>[^']+)'!(?P<col>\$?[A-Z]{1,3})(?P<row>\$?\d+)")


# ------------------------------------------------------------------ 基本工具
def norm_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


def compare_values(a, b, tol):
    """回傳 'exact' / 'tol' / None(None 代表不同)。"""
    a, b = norm_text(a), norm_text(b)
    if a == b and type(a) is type(b) or a == b:
        return "exact"
    if (isinstance(a, (int, float)) and not isinstance(a, bool)
            and isinstance(b, (int, float)) and not isinstance(b, bool)):
        if tol and math.isclose(a, b, rel_tol=tol, abs_tol=tol):
            return "tol"
    return None


def normalize_formula(f, raw_name, base_row):
    """把參照 raw_name 的列號換成相對位移,例如 'X_Rawdata'!A5 -> 'X_Rawdata'!A[+0]"""
    if not (isinstance(f, str) and f.startswith("=")):
        return f

    def repl(m):
        if m.group("sheet") != raw_name:
            return m.group(0)
        n = int(m.group("row").lstrip("$"))
        return f"'{m.group('sheet')}'!{m.group('col')}[{n - base_row:+d}]"

    return REF_RE.sub(repl, f)


def detect_offset(ws, raw_name):
    """可見表第 r 列參照 raw 第 n 列 → 位移 = r - n(即標題列數)。找不到回傳 None。"""
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                for m in REF_RE.finditer(c.value):
                    if m.group("sheet") == raw_name:
                        return c.row - int(m.group("row").lstrip("$"))
    return None


# ------------------------------------------------------------------ 可見表索引
def build_index(ws, offset):
    """
    回傳 {row_id: 列號}。row_id = (A, B, C, 第幾次出現, 區塊內第幾列)
    只有區塊第一列有 A,後面列沿用同一個 key。
    """
    index = {}
    seen = Counter()
    cur, k = None, 0
    for r in range(offset + 1, ws.max_row + 1):
        key = tuple(norm_text(ws.cell(r, c).value) for c in KEY_COLS)
        if key[0] is not None:
            seen[key] += 1
            cur, k = (key, seen[key]), 0
        else:
            if cur is None:
                continue
            if all(ws.cell(r, c).value is None for c in range(1, ws.max_column + 1)):
                continue
            k += 1
        index[(cur[0], cur[1], k)] = r
    return index


def fmt_key(row_id):
    key, occ, k = row_id
    s = " | ".join("" if x is None else str(x) for x in key)
    if occ > 1:
        s += f"  (重複key第{occ}筆)"
    if k:
        s += f"  [區塊第{k + 1}列]"
    return s


# ------------------------------------------------------------------ 主要比對
def compare_visible(wsa, wsb, name, raw_name, off_a, off_b, tol, diffs, stats):
    ia, ib = build_index(wsa, off_a), build_index(wsb, off_b)
    only_a = [k for k in ia if k not in ib]
    only_b = [k for k in ib if k not in ia]
    ncol = max(wsa.max_column, wsb.max_column)

    # 標題列(位移以內的列)直接按位置比
    for r in range(1, off_a + 1):
        for c in range(1, ncol + 1):
            va, vb = wsa.cell(r, c).value, wsb.cell(r, c).value
            res = compare_values(va, vb, tol)
            stats[name]["cells"] += 1
            if res is None:
                stats[name]["diff"] += 1
                diffs.append((name, "標題列", r, r, get_column_letter(c), va, vb))
            elif res == "tol":
                stats[name]["tol"] += 1

    for rid in ia:
        if rid not in ib:
            continue
        ra, rb = ia[rid], ib[rid]
        for c in range(KEY_COLS[-1] + 1, ncol + 1):
            va, vb = wsa.cell(ra, c).value, wsb.cell(rb, c).value
            if raw_name:
                va = normalize_formula(va, raw_name, ra - off_a)
                vb = normalize_formula(vb, raw_name, rb - off_b)
            res = compare_values(va, vb, tol)
            stats[name]["cells"] += 1
            if res is None:
                stats[name]["diff"] += 1
                diffs.append((name, fmt_key(rid), ra, rb, get_column_letter(c), va, vb))
            elif res == "tol":
                stats[name]["tol"] += 1
    return ia, ib, only_a, only_b


def compare_raw(wsa, wsb, name, ia, ib, off_a, off_b, tol, diffs, stats, label):
    ncol = max(wsa.max_column, wsb.max_column)
    matched_rows = set()
    for rid in ia:
        if rid not in ib:
            continue
        ra, rb = ia[rid] - off_a, ib[rid] - off_b
        matched_rows.add(ra)
        for c in range(1, ncol + 1):
            va, vb = wsa.cell(ra, c).value, wsb.cell(rb, c).value
            res = compare_values(va, vb, tol)
            stats[name]["cells"] += 1
            if res is None:
                stats[name]["diff"] += 1
                diffs.append((name, fmt_key(rid), ra, rb, get_column_letter(c), va, vb))
            elif res == "tol":
                stats[name]["tol"] += 1
    # 兩邊的列數是否一樣(避免漏比)
    stats[name]["rows_a"] = wsa.max_row
    stats[name]["rows_b"] = wsb.max_row


def run(path_a, path_b, tol, only_sheets=None):
    wa = openpyxl.load_workbook(path_a)  # 保留公式字串
    wb = openpyxl.load_workbook(path_b)
    names_a, names_b = wa.sheetnames, wb.sheetnames
    diffs, one_side = [], []
    stats = defaultdict(lambda: {"cells": 0, "diff": 0, "tol": 0})
    notes = []

    for n in names_a:
        if n not in names_b:
            notes.append(f"工作表只在檔案1:{n}")
    for n in names_b:
        if n not in names_a:
            notes.append(f"工作表只在檔案2:{n}")

    common = [n for n in names_a if n in names_b]
    visible = [n for n in common if not n.endswith(RAW_SUFFIX)]
    raws = {n for n in common if n.endswith(RAW_SUFFIX)}

    for name in visible:
        if only_sheets and name not in only_sheets:
            continue
        raw_name = name + RAW_SUFFIX
        has_raw = raw_name in raws
        wsa, wsb = wa[name], wb[name]
        off_a = detect_offset(wsa, raw_name) if has_raw else None
        off_b = detect_offset(wsb, raw_name) if has_raw else None
        if off_a is None or off_b is None:
            off_a = off_b = 2 if off_a is None and off_b is None else (off_a or off_b)
            notes.append(f"[{name}] 無法由公式判斷標題列數,改用 {off_a}")
        ia, ib, oa, ob = compare_visible(
            wsa, wsb, name, raw_name if has_raw else None, off_a, off_b, tol, diffs, stats)
        for rid in oa:
            one_side.append((name, "只在檔案1", fmt_key(rid), ia[rid]))
        for rid in ob:
            one_side.append((name, "只在檔案2", fmt_key(rid), ib[rid]))
        if has_raw:
            compare_raw(wa[raw_name], wb[raw_name], raw_name, ia, ib, off_a, off_b,
                        tol, diffs, stats, name)
        stats[name]["only_a"] = len(oa)
        stats[name]["only_b"] = len(ob)
        stats[name]["matched_rows"] = len(set(ia) & set(ib))
        stats[name]["total_a"] = len(ia)
        stats[name]["total_b"] = len(ib)

    # 沒有對應可見表的 raw 表,提醒一下
    for rn in raws:
        base = rn[: -len(RAW_SUFFIX)]
        if base not in common:
            notes.append(f"[{rn}] 找不到對應的可見工作表,未比對")
    return stats, diffs, one_side, notes


# ------------------------------------------------------------------ 輸出
def write_report(path, path_a, path_b, stats, diffs, one_side, notes):
    wb = openpyxl.Workbook()
    bold = Font(bold=True)
    red = PatternFill("solid", fgColor="FFC7CE")

    ws = wb.active
    ws.title = "摘要"
    ws.append(["檔案1", path_a])
    ws.append(["檔案2", path_b])
    ws.append([])
    ws.append(["工作表", "配對到的key數", "檔案1的key數", "檔案2的key數", "只在檔案1", "只在檔案2",
               "比對儲存格數", "有差異", "僅浮點誤差(視為相同)"])
    for c in ws[4]:
        c.font = bold
    for name, s in stats.items():
        ws.append([name, s.get("matched_rows", ""), s.get("total_a", ""), s.get("total_b", ""),
                   s.get("only_a", ""), s.get("only_b", ""), s["cells"], s["diff"], s["tol"]])
        if s["diff"] or s.get("only_a") or s.get("only_b"):
            for c in ws[ws.max_row]:
                c.fill = red
    for n in notes:
        ws.append([n])
    ws.column_dimensions["A"].width = 40

    wd = wb.create_sheet("差異明細")
    wd.append(["工作表", "key (A | B | C)", "檔案1列", "檔案2列", "欄", "檔案1的值", "檔案2的值"])
    for c in wd[1]:
        c.font = bold
    for d in diffs:
        wd.append([("'" + str(x) if isinstance(x, str) and x.startswith("=") else x) for x in d])
    for col, w in zip("ABCDEFG", (34, 60, 9, 9, 6, 40, 40)):
        wd.column_dimensions[col].width = w
    wd.freeze_panes = "A2"

    wo = wb.create_sheet("只存在一邊的key")
    wo.append(["工作表", "位置", "key", "列號"])
    for c in wo[1]:
        c.font = bold
    for r in one_side:
        wo.append(list(r))
    wo.column_dimensions["C"].width = 70
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description="以 A、B、C 欄為 key 比對兩個列順序不同的 Excel")
    ap.add_argument("file1")
    ap.add_argument("file2")
    ap.add_argument("--out", default="比對結果.xlsx", help="差異報告輸出檔")
    ap.add_argument("--tol", type=float, default=1e-9, help="數值容許誤差(預設 1e-9)")
    ap.add_argument("--exact", action="store_true", help="數值也要完全相同(不容許浮點誤差)")
    ap.add_argument("--sheets", nargs="*", help="只比對指定的可見工作表(Rawdata 會一起比)")
    args = ap.parse_args()

    tol = 0 if args.exact else args.tol
    stats, diffs, one_side, notes = run(args.file1, args.file2, tol, args.sheets)

    print(f"{'工作表':<34}{'key配對':>8}{'僅一邊':>8}{'儲存格':>9}{'差異':>8}{'浮點誤差':>9}")
    total_diff = len(one_side)
    for name, s in stats.items():
        side = s.get("only_a", 0) + s.get("only_b", 0)
        print(f"{name:<34}{s.get('matched_rows', ''):>8}{side if 'matched_rows' in s else '':>8}"
              f"{s['cells']:>9}{s['diff']:>8}{s['tol']:>9}")
        total_diff += s["diff"]
    for n in notes:
        print("注意:", n)
        total_diff += 1 if n.startswith("工作表只在") else 0

    write_report(args.out, args.file1, args.file2, stats, diffs, one_side, notes)
    print(f"\n差異共 {len(diffs)} 格、只存在一邊的 key {len(one_side)} 筆 → 詳見 {args.out}")
    print("結果:", "完全一致 ✔" if total_diff == 0 else "有差異 ✘")
    sys.exit(0 if total_diff == 0 else 1)


if __name__ == "__main__":
    main()