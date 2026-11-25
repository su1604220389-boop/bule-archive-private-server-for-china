#!/bin/bash
# Click-validity gate: did the client actually POST /api/account/auth recently?
SECS=${1:-60}
python3 - "$SECS" <<'PY'
import json, sys, datetime
secs=int(sys.argv[1])
rows=[json.loads(l) for l in open('/www/wwwroot/bapatch/logs/api_all_requests.log') if l.strip()]
now=datetime.datetime.now()
hits=[]
for d in rows:
    try: t=datetime.datetime.strptime(d.get('t'),'%Y-%m-%d %H:%M:%S')
    except Exception: continue
    ua=str((d.get('headers') or {}).get('User-Agent') or (d.get('headers') or {}).get('user-agent') or '')
    if 'BestHTTP' in ua and (now-t).total_seconds() <= secs:
        hits.append((d.get('t'), d.get('path'), d.get('resp_code'), d.get('resp_len'), d.get('wrap_mode')))
if hits:
    print('GATE=PASS  client POSTed within %ds: %d hit(s)' % (secs, len(hits)))
    for h in hits: print('   ', h)
else:
    print('GATE=FAIL  no client POST within %ds -> ROUND INVALID' % secs)
PY
