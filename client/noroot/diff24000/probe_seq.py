import json,glob,os
d=r"report\_tmp\official_decoded_201"
for n in ["00_1002_api_account_auth","01_24000_api_academy_getinfo","02_1017_api_account_loginsync","03_4000_api_item_list"]:
    for suf in ("request","response"):
        p=os.path.join(d,f"{n}.{suf}.json")
        if not os.path.exists(p): print(n,suf,"MISSING"); continue
        o=json.load(open(p,encoding="utf-8"))
        m=o.get("meta",{})
        pl=o.get("plain")
        print(f"{n}.{suf}: id={m.get('id')} bj={m.get('bj')} status={m.get('status')} resp_bytes={m.get('resp_bytes')} proto={m.get('protocol')} plain_len={len(pl) if isinstance(pl,str) else type(pl).__name__}")
        if suf=="request" and isinstance(pl,str):
            print("   req plain[:260]:", pl[:260].replace("\n"," "))
    print()
