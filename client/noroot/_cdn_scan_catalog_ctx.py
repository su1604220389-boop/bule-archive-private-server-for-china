# -*- coding: utf-8 -*-
"""catalog.json 里 {PlatformUtils.AddressableLoadPath} 的出现次数与上下文"""
import re, zipfile

apk = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'
z = zipfile.ZipFile(apk)

PH = b'{PlatformUtils.AddressableLoadPath}'
subs = [b'/AssetBundles/', b'Manifest/', b'Catalog/', b'Android/', b'/Audio', b'/uis', b'/video']

occ = []
count_ph = 0
count_sub = {s: 0 for s in subs}
samples = []
CH = 8 << 20
off = 0
with z.open('assets/aa/catalog.json') as f:
    carry = b''
    while True:
        chunk = f.read(CH)
        if not chunk:
            break
        buf = carry + chunk
        base = off - len(carry)
        for m in re.finditer(re.escape(PH), buf):
            count_ph += 1
            if len(occ) < 5:
                occ.append(base + m.start())
        for s in subs:
            count_sub[s] += buf.count(s)
        # 收集第一个占位符附近的上下文
        if len(samples) < 3:
            m = re.search(re.escape(PH) + rb'.{0,220}', buf, re.S)
            if m:
                samples.append((base + m.start(), m.group()))
        carry = buf[-512:]
        off += len(chunk)

print("占位符出现次数: %d" % count_ph)
print("前几个偏移: %s" % [hex(o) for o in occ])
for s in subs:
    print("  子串 %-14s 出现 %d 次" % (s.decode(), count_sub[s]))

print("\n=== 上下文样本 ===")
for o, s in samples:
    print("\n@0x%08x" % o)
    print(s.decode('latin1'))
