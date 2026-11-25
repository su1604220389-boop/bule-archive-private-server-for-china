import sys, json, datetime
sys.path.insert(0,r"work\ba\server\deploy")
import gen24000 as G
o=json.load(open(r"report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json",encoding="utf-8"))
inn=o["inner"]; m=o["meta"]
t=inn["ServerTimeTicks"]
dt=G.b24000_time_from_ticks(t)
print("官方 ServerTimeTicks :", t)
print("  反算 datetime      :", dt.isoformat())
print("  抓包 meta.bj       :", m["bj"], "  <- 同一时刻 => ticks 编码的是**本地墙钟(UTC+8)**，不是 UTC")
print("  若当 UTC 解读      :", (dt - datetime.timedelta(hours=8)).isoformat(), "(=UTC+8 减 8h)")
print()
print("  官方 LastUpdate    :", inn["AcademyDB"]["LastUpdate"])
lu=datetime.datetime.fromisoformat(inn["AcademyDB"]["LastUpdate"])
print("  LastUpdate 落后 ticks-derived:", dt-lu)
print()
print("官方 ticks 的毫秒位 :", t % 10_000_000, " (100ns) -> ms =", (t%10_000_000)//10_000)
print()
print("== LastUpdate 格式：尾零裁剪的影响 ==")
import collections
cnt=collections.Counter()
for k in range(1000):
    d=datetime.datetime(2026,11,16,6,13,47,880000)+datetime.timedelta(milliseconds=k)
    s=G.b24000_fmt_time(d)
    cnt[len(s.split('.')[1]) if '.' in s else 0]+=1
print("  小数位数分布(0..3):", dict(sorted(cnt.items())), " -> 非3位占比 %.1f%%" % (100*(1000-cnt.get(3,0))/1000))
for k in (0,10,100,250,479):
    d=datetime.datetime(2026,11,16,6,13,47,880000)+datetime.timedelta(milliseconds=k)
    print("    sample ms=%-3d -> %r" % (880+k if 880+k<1000 else 0, G.b24000_fmt_time(d)))
