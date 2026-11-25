#!/usr/bin/env python3
# gwstate probe: log every request (headers+body) then serve the live DTO A file unchanged
import http.server, socketserver, json, time, os

LOG  = '/www/wwwroot/bapatch/logs/gwstate_requests.log'
BODY = '/www/wwwroot/_ba_state/gw/api-state.json'

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _log(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else b''
        rec = {
            't': time.strftime('%Y-%m-%d %H:%M:%S'),
            'from': self.client_address[0],
            'reqline': self.requestline,
            'headers': dict(self.headers.items()),
            'body_len': len(body),
            'body_hex': body[:1024].hex(),
        }
        try:
            with open(LOG, 'a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def _serve(self):
        self._log()
        try:
            b = open(BODY, 'rb').read() if os.path.exists(BODY) else b'{}'
        except Exception:
            b = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    do_GET = _serve
    do_POST = _serve

    def log_message(self, *a):
        pass

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('127.0.0.1', 9098), H) as s:
    s.serve_forever()
