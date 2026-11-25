import json,glob,os,statistics
ratios=[]
for p in glob.glob(r"report\_tmp\official_decoded_201\*.response.json"):
    try: o=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    m=o.get("meta") or {}; pl=o.get("plain"); rb=m.get("resp_bytes")
    if not isinstance(pl,str) or not rb: continue
    ratios.append((rb/len(pl), os.path.basename(p), rb, len(pl)))
ratios.sort()
print("resp_bytes / plain_len  (n=%d)" % len(ratios))
print("  min=%.4f  median=%.4f  max=%.4f" % (ratios[0][0], statistics.median([r[0] for r in ratios]), ratios[-1][0]))
for r in ratios[:2]+ratios[-2:]:
    print("   %.4f  rb=%-7d plain=%-7d %s" % (r[0],r[2],r[3],r[1]))
med=statistics.median([r[0] for r in ratios])
print()
print("若我们的 wire=1772 B  -> plain ≈ %.0f B  -> inner ≈ ?" % (1772/med))
# inner vs plain overhead on the 24000 capture
o=json.load(open(r"report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json",encoding="utf-8"))
inner=len(json.dumps(o["inner"],ensure_ascii=False,separators=(",",":")))
pl=len(o["plain"])
print("官方 24000: inner=%d plain=%d overhead=%d  inner/plain=%.4f" % (inner,pl,pl-inner,inner/pl))
print("若 plain=%.0f -> inner ≈ %.0f B" % (1772/med,(1772/med)*(inner/pl)))
