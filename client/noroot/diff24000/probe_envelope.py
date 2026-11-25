import json
p=r"report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json"
o=json.load(open(p,encoding="utf-8")); pl=o["plain"]
print("plain head 120:", pl[:120])
print("plain tail 120:", pl[-120:])
d=json.loads(pl)
print("plain outer keys:", list(d.keys()))
print("protocol value:", repr(d.get("protocol")))
pk=d.get("packet")
print("packet type:", type(pk).__name__, "len:", len(pk) if isinstance(pk,str) else None)
print()
print("=== 02 loginsync request full plain ===")
p2=r"report\_tmp\official_decoded_201\02_1017_api_account_loginsync.request.json"
o2=json.load(open(p2,encoding="utf-8")); pl2=o2["plain"]
r2=json.loads(pl2)
print("outer keys:", list(r2.keys()), "protocol:", repr(r2.get("protocol")))
pk2=r2.get("packet")
q=json.loads(pk2) if isinstance(pk2,str) else pk2
print("inner keys:", list(q.keys()))
print("Protocol:", q.get("Protocol"), "  Hash>>32:", q.get("Hash")>>32 if isinstance(q.get("Hash"),int) else None)
print("SyncProtocols:", q.get("SyncProtocols"))
print("SkillCutInOption:", repr(q.get("SkillCutInOption")))
print("SessionKey:", json.dumps(q.get("SessionKey"),ensure_ascii=False))
print("AccountId:", q.get("AccountId"), "OSType:", q.get("OSType"), "Resendable:", q.get("Resendable"), "IsTest:", q.get("IsTest"))
