"""
比對「原版」與「優化版」data_analysis 的輸出是否一致(含 dtype)。
用法: python test_data_analysis_equiv.py <原版專案根目錄> <優化版專案根目錄>
"""
import sys, importlib.util, random, time
import pandas as pd, numpy as np

def load(root, tag):
    sys.path.insert(0, root)
    sys.modules.pop("common", None); sys.modules.pop("common.util", None)
    spec = importlib.util.spec_from_file_location(f"da_{tag}", f"{root}/analysis/data_analysis.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); sys.path.pop(0); return m

orig, new = load(sys.argv[1], "o"), load(sys.argv[2], "n")
random.seed(3)

def mk(n):
    orgs=[f"TWU{i:06d}_1900_2300" for i in range(60)]
    return pd.DataFrame([(random.choice(orgs), random.choice([1,2,3,5,9]), random.choice(['2024-03-12','2025-03-13']), random.randint(0,50))
                         for _ in range(n)], columns=['Inst','FID','Ver','PaperCount'])

ok = True
for n in (1, 7, 500, 5000):
    df = mk(n)
    a, b = orig.a02_sumup_calculate(df.copy()), new.a02_sumup_calculate(df.copy())
    same = a.equals(b) and list(a.dtypes.astype(str)) == list(b.dtypes.astype(str)) and list(a.columns) == list(b.columns)
    ok &= same; print(f"a02 n={n:5}: equal={same}")
# 單一主題欄
df = pd.DataFrame({'Inst':['a','b','a','c'],'v':[1,2,3,4]})
same = orig.a02_sumup_calculate(df.copy()).equals(new.a02_sumup_calculate(df.copy())); ok &= same; print("a02 1 subject col:", same)

for dec in (-1, 2, 4):
    df = pd.DataFrame({'k':list('abcdef'),'cited':[10,0,7,5,100,3],'num':[3,0,7,2,9,0]})
    a, b = orig.a08_cntavg_calculate(df, dec), new.a08_cntavg_calculate(df, dec)
    same = np.allclose(a['CntAvg'].astype(float), b['CntAvg'].astype(float), equal_nan=True) and list(a.columns)==list(b.columns)
    ok &= same; print(f"a08 decimals={dec}: equal={same}")

# growth rate (pure python path)
def pre(y): return str(int(y)-1)
df = pd.DataFrame({'org':['A']*4+['B']*4,'year':['2020','2021','2022','2023']*2,'cnt':[10,12,0,5,3,3,6,'N/A']})
a = orig.growth_rate_calculate(df, 1, ['2021','2022','2023'], pre, True)
b = new.growth_rate_calculate(df, 1, ['2021','2022','2023'], pre, True)
same = a.astype(str).equals(b.astype(str)); ok &= same; print("growth_rate (valid data): equal =", same)
df.loc[2,'cnt'] = None
try: orig.growth_rate_calculate(df, 1, ['2021','2022','2023'], pre, True); print("orig with NULL value: ok")
except Exception as e: print("orig with NULL value ->", type(e).__name__)
print("new  with NULL value ->", new.growth_rate_calculate(df, 1, ['2021','2022','2023'], pre, True)['cnt'].tolist())

# performance
big = mk(30000)
t=time.perf_counter(); orig.a02_sumup_calculate(big.copy()); to=time.perf_counter()-t
t=time.perf_counter(); new.a02_sumup_calculate(big.copy()); tn=time.perf_counter()-t
print(f"a02 30000 rows: orig {to:.2f}s -> new {tn:.3f}s")
# b06 (original is broken)
h = pd.DataFrame({'org':['A']*5+['B']*3,'id':range(8),'cited':[10,8,5,4,3, 1,1,0]})
try: orig.b06_h_index_calculate(h); print("orig b06 ok")
except Exception as e: print("orig b06 ->", type(e).__name__)
print("new b06 ->", new.b06_h_index_calculate(h).values.tolist(), "(期望 A=4, B=1)")
print("\nALL EQUIVALENT:", ok)
