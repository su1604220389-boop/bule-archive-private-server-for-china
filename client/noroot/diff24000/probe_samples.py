import json,glob,os,re
pat=re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
files=sorted(set(glob.glob(r"report\_tmp\t24000*.json")+glob.glob(r"work\ba\server\deploy\out\*24000*.json")+glob.glob(r"report\_tmp\sandbox292\academy_24000_official.json")+glob.glob(r"work\ba\noroot\diff24000\*.json")))
for p in files:
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception as e: print(os.path.basename(p),"ERR",e); continue
    if isinstance(d,dict) and "inner" in d and isinstance(d["inner"],dict): d=d["inner"]
    if not isinstance(d,dict): print(os.path.basename(p),"not dict"); continue
    sk=d.get("SessionKey"); sk=sk if isinstance(sk,dict) else {}
    tok=str(sk.get("MxToken") or "")
    adb=d.get("AcademyDB") if isinstance(d.get("AcademyDB"),dict) else {}
    locs=d.get("AcademyLocationDBs"); locs=locs if isinstance(locs,list) else []
    z=adb.get("ZoneVisitCharacterDBs")
    ztot=sum(len(v) for v in z.values()) if isinstance(z,dict) else ("LIST" if isinstance(z,list) else "?")
    l0=locs[0] if locs and isinstance(locs[0],dict) else {}
    print("%-40s aid=%-12s toklen=%-3d uuid=%-5s locs=%-2d zelem=%-6s acctid=%-12s loc0.AccId=%s"
          % (os.path.basename(p)[:40], sk.get("AccountServerId"), len(tok), bool(pat.match(tok)),
             len(locs), ztot, adb.get("AccountId"), l0.get("AccountId")))
    print("     LastUpdate=%r" % (adb.get("LastUpdate"),))
