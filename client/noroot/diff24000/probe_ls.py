import json
p2=r"report\_tmp\official_decoded_201\02_1017_api_account_loginsync.request.json"
o2=json.load(open(p2,encoding="utf-8")); q=json.loads(o2["plain"])
print("Protocol value:", q.get("Protocol"), " Hash>>32:", (q["Hash"]>>32))
print("Hash low32:", q["Hash"] & 0xFFFFFFFF)
print("SyncProtocols count:", len(q["SyncProtocols"]))
print("SessionKey:", json.dumps(q.get("SessionKey"),ensure_ascii=False))
print("AccountId:", q.get("AccountId"), "OSType:", q.get("OSType"))
print()
# verify envelope serialization hypothesis on official 24000 response
p=r"report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json"
o=json.load(open(p,encoding="utf-8")); pl=o["plain"]; d=json.loads(pl)
rec=json.dumps({"protocol":d["protocol"],"packet":d["packet"],"requestid":d["requestid"]},
               ensure_ascii=False,separators=(",",":"))
print("recon plain len:", len(rec), " official plain len:", len(pl), " EQUAL:", rec==pl)
