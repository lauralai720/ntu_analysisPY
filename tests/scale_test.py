import sys, os, re, random, sqlite3, math, time
root = sys.argv[1]
sys.path.insert(0, root); sys.path.append(os.path.dirname(__file__))
from database.sql import SQLExecute
random.seed(7)
con = sqlite3.connect(":memory:")
con.executescript("""CREATE TABLE WOS_ORG (ISI_ID TEXT, AddressIndex INT, OrgName TEXT, Country TEXT, Reprint INT);
CREATE TABLE WOS_ORG_2nd (ISI_ID TEXT, AddressIndex INT, OrgName TEXT, Country TEXT, Reprint INT);
CREATE TABLE WOS_AUTHOR_ORG_RELATION (ISI_ID TEXT, AuthorIndex INT, AddressIndex INT, Reprint INT);""")
second = sorted({f"TWU{random.randint(1,9):06d}{d:02d}{s:02d}00" for d in range(1,60) for s in range(0,20) for _ in [0]})
r1,r2,ra=[],[],[]
for i in range(1500):
    isi=f"WOS:{i:09d}"
    for addr in range(1, random.randint(2,4)):
        rp=random.choice([0,1]); r1.append((isi,addr,"TWU000001","TW",rp))
        for _ in range(random.randint(1,3)): r2.append((isi,addr,random.choice(second),"TW",rp))
        for a in range(1,random.randint(2,4)): ra.append((isi,a,addr,rp))
con.executemany("INSERT INTO WOS_ORG VALUES (?,?,?,?,?)",r1); con.executemany("INSERT INTO WOS_ORG_2nd VALUES (?,?,?,?,?)",r2)
con.executemany("INSERT INTO WOS_AUTHOR_ORG_RELATION VALUES (?,?,?,?)",ra)
executed=[]
def tr(sql):
    sql=re.sub(r"\[[^\]]+\]\.dbo\.\[([^\]]+)\]",r"\1",sql).replace("N'","'").replace("#TEMPTBL","TEMPTBL")
    m=re.match(r"SELECT TOP 0 (.*) INTO (\S+) FROM (.*)$",sql,re.S)
    if m: sql=f"CREATE TABLE {m.group(2)} AS SELECT {m.group(1)} FROM {m.group(3)} LIMIT 0"
    return re.sub(r"\(VALUES (.*?)\) AS K\(\[k\],\[p\]\)",lambda m:f"(SELECT column1 AS [k], column2 AS [p] FROM (VALUES {m.group(1)})) AS K",sql,flags=re.S)
def dn(sql,*a,**k): executed.append(sql); con.execute(tr(sql))
SQLExecute.do_no_query=staticmethod(dn); SQLExecute.commit=staticmethod(lambda:None)

import common.db_schema as db_schema
from components.subject_info import WOSPaperOrgSubjectInfo
from components.paper_org_value import PaperOrgSelectedValue, PaperOrgSelectItem, AuthorIndex
db_schema.schema=db_schema.WOSSchema(); db_schema.schema.set_DB_name("dbx")
N=900
sel=PaperOrgSelectedValue(); sel.add(PaperOrgSelectItem("TWU000001","校","U"))
pats=random.sample(second,N)
for s in pats: sel.add(PaperOrgSelectItem(s,"x","y"))
info=WOSPaperOrgSubjectInfo.__new__(WOSPaperOrgSubjectInfo); info.orgs_selected_list=["x"]; info.order_orgs_selected_list=[]
t=time.perf_counter(); subj,_,_,_,_=info.get_subject(sel, author_index=AuthorIndex.FirstOrReprint); dt=time.perf_counter()-t
tmp=subj.temp_table_name.replace("#","")
cols=[r[1] for r in con.execute(f"PRAGMA table_info({tmp})")]
got={tuple(sorted(zip(cols,map(str,r)))) for r in con.execute(f"SELECT * FROM {tmp}")}

# ---- 純 Python 參考解 ----
aor={}
for isi,au,ad,rp in ra: aor.setdefault((isi,ad,rp),[]).append(au)
ok_aor=lambda key: any(True for au in aor.get(key,[])) and (key[2]==1 or any(a==1 for a in aor[key]))   # FirstOrReprint: AuthorIndex=1 OR Reprint=1
org1={(i,a,r) for i,a,_,_,r in r1}
ref=set()
def add(key,table_rows,pattern,like):
    for isi,ad,name,_,rp in table_rows:
        if (name==pattern) or (like and pattern.endswith("%") and name.startswith(pattern[:-1])):
            k=(isi,ad,rp)
            if k in aor and ok_aor(k) and k in org1:
                ref.add(tuple(sorted([("wos_org_OrgDesc",key),("wos_org_ISI_ID",isi),("wos_org_AddressIndex",str(ad)),("wos_org_Reprint",str(rp))])))
add("TWU000001_1900_2300", r1, "TWU000001", False)
for s in pats: add(f"{s}_1900_2300", r2, s, True)
print(f"keys={len(subj.subj_vals)}  SQL statements={len(executed)} (1 CREATE + {len(executed)-1} INSERT; 原版會是 {len(subj.subj_vals)+1})")
print(f"rows={len(got)}  equals_python_reference={got==ref}  (python {dt:.2f}s incl. sqlite)")
