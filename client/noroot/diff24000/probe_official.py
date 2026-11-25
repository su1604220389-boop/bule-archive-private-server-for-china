import json, base64, collections
p=r"report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json"
d=json.load(open(p,encoding="utf-8")); inn=d["inner"]
sk=inn["SessionKey"]; adb=inn["AcademyDB"]
print("SessionKey:", json.dumps(sk,ensure_ascii=False))
print("  MxToken len:", len(sk["MxToken"]), "chars")
try:
    raw=base64.b64decode(sk["MxToken"], validate=True); print("  b64 decode OK ->", len(raw), "bytes")
except Exception as e: print("  b64 decode FAIL:", e)
print()
print("AcademyDB keys:", list(adb.keys()))
print("  AccountId:", adb["AccountId"], type(adb["AccountId"]).__name__)
print("  LastUpdate:", repr(adb["LastUpdate"]))
print("  ZoneScheduleGroupRecords:", type(adb["ZoneScheduleGroupRecords"]).__name__, "len=",len(adb["ZoneScheduleGroupRecords"]))
z=adb["ZoneVisitCharacterDBs"]
print("  ZoneVisitCharacterDBs: type",type(z).__name__,"len",len(z))
dist=collections.Counter(len(v) for v in z.values())
print("  length distribution:", dict(sorted(dist.items())))
print("  total elements:", sum(len(v) for v in z.values()))
print("  empty keys:", [k for k,v in z.items() if len(v)==0])
print("  keys (sorted as-is):", list(z.keys()))
print("  key dtype:", set(type(k).__name__ for k in z))
print("  element dtype:", set(type(x).__name__ for v in z.values() for x in v))
print()
print("AcademyLocationDBs len:", len(inn["AcademyLocationDBs"]))
for i,r in enumerate(inn["AcademyLocationDBs"]):
    print("  [%d]"%i, json.dumps(r,ensure_ascii=False), "keys=",list(r.keys()))
print()
print("ServerTimeTicks:", inn["ServerTimeTicks"], "digits", len(str(inn["ServerTimeTicks"])))
print("ServerNotification:", inn["ServerNotification"], "RequestId:", inn["RequestId"], "len", len(inn["RequestId"]))
print("Protocol:", inn["Protocol"])
