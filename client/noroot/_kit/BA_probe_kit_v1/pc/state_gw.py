#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BA Prober v1  --  CONNECT proxy + self-signed TLS terminator + fake /api/state
Pure stdlib. No third-party deps.

Modes
  passthrough : log CONNECT target + parse TLS ClientHello SNI, then tunnel to the real
                server unchanged. 100% passive. Use this first to learn the real hostnames.
  logonly     : log the CONNECT target and immediately answer 502. The fastest possible
                hostname harvest (20 s), no tunnel, no internet needed on the PC.
  tls         : terminate TLS with our own cert, dump every HTTP request, and answer
                /api/state with a JSON we control (Servers -> our own gateway).

Usage
  python state_gw.py --mode passthrough --port 7890
  python state_gw.py --mode tls --port 7890 --cert ../pc/certs/leaf.crt --key ../pc/certs/leaf.key
  python state_gw.py --mode tls --port 7890 --cert ... --key ... --servers http://127.0.0.1:5000/api/ --state 0

Every connection is appended to logs/session_YYYYmmdd_HHMMSS.log and echoed to stdout.
"""

import argparse
import json
import os
import socket
import ssl
import struct
import sys
import threading
import time
from datetime import datetime

LOG_LOCK = threading.Lock()
LOG_FH = None
ARGS = None


# ---------------------------------------------------------------- logging
def log(tag, msg):
    line = "[%s] %-9s %s" % (datetime.now().strftime("%H:%M:%S.%f")[:-3], tag, msg)
    with LOG_LOCK:
        print(line, flush=True)
        if LOG_FH:
            LOG_FH.write(line + "\n")
            LOG_FH.flush()


def hexdump(b, limit=512):
    b = b[:limit]
    out = []
    for i in range(0, len(b), 16):
        chunk = b[i:i + 16]
        hx = " ".join("%02x" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        out.append("    %08x  %-47s  %s" % (i, hx, asc))
    if len(b) == limit:
        out.append("    ... (truncated at %d)" % limit)
    return "\n".join(out)


# ------------------------------------------------------- TLS ClientHello SNI
def parse_sni(b):
    """Return SNI hostname from a TLS ClientHello, or None. Never raises."""
    try:
        if len(b) < 5 or b[0] != 0x16:
            return None
        # TLS record: type(1) ver(2) len(2)
        rec_len = struct.unpack(">H", b[3:5])[0]
        body = b[5:5 + rec_len]
        if len(body) < 4 or body[0] != 0x01:
            return None
        # handshake: type(1) len(3) ver(2) random(32)
        p = 4 + 2 + 32
        sid_len = body[p]
        p += 1 + sid_len
        cs_len = struct.unpack(">H", body[p:p + 2])[0]
        p += 2 + cs_len
        comp_len = body[p]
        p += 1 + comp_len
        if p + 2 > len(body):
            return None
        ext_total = struct.unpack(">H", body[p:p + 2])[0]
        p += 2
        end = min(p + ext_total, len(body))
        while p + 4 <= end:
            etype, elen = struct.unpack(">HH", body[p:p + 4])
            p += 4
            data = body[p:p + elen]
            p += elen
            if etype == 0 and len(data) >= 5:  # server_name
                # list_len(2) type(1) name_len(2) name
                nlen = struct.unpack(">H", data[3:5])[0]
                return data[5:5 + nlen].decode("ascii", "replace")
        return None
    except Exception:
        return None


NETERR = (socket.timeout, OSError)


def peek_client_hello(sock, timeout=3.0):
    sock.settimeout(timeout)
    try:
        b = sock.recv(4096)
    except NETERR:
        return b"", None
    return b, parse_sni(b)


# ---------------------------------------------------------------- helpers
def recv_until(sock, marker=b"\r\n\r\n", maxb=65536):
    buf = b""
    while marker not in buf and len(buf) < maxb:
        try:
            chunk = sock.recv(4096)
        except NETERR:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def pipe(a, b, tag):
    """copy both directions until EOF"""
    def one(src, dst, way):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass
    t = threading.Thread(target=one, args=(a, b, tag), daemon=True)
    t.start()
    return t


def handle_http_connect_tunnel(cli, host, port):
    try:
        up = socket.create_connection((host, port), timeout=10)
    except Exception as e:
        log("CONNFAIL", "%s:%d  %s" % (host, port, e))
        try:
            cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        return
    cli.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
    log("TUNNEL", "%s:%d  opened" % (host, port))
    t = pipe(cli, up, "tunnel")
    t.join(timeout=180)
    try:
        up.close()
    except Exception:
        pass


# ---------------------------------------------------------------- fake state
def fake_state(servers, state_value, msg, catalog):
    return json.dumps({
        "Servers": servers,
        "State": state_value,
        "Msg": msg,
        "CallbackUrl": "",
        "CustomerServiceUrl": "",
        "AddressablesCatalogUrlRoots": catalog,
    }, ensure_ascii=False).encode("utf-8")


def http_response(body, code="200 OK", extra=None):
    hdrs = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
        "Connection": "close",
    }
    if extra:
        hdrs.update(extra)
    head = "HTTP/1.1 %s\r\n" % code
    for k, v in hdrs.items():
        head += "%s: %s\r\n" % (k, v)
    head += "\r\n"
    return head.encode("ascii") + body


def handle_tls_terminated(cli, host, raw):
    """raw = the ClientHello bytes we already read (may be empty)"""
    ctx = ARGS._ctx
    try:
        tls = ctx.wrap_socket(cli, server_side=True)
    except ssl.SSLError as e:
        log("TLS-REJECT", "%s : %s  <-- client refused our cert (that IS the answer to E4)" % (host, e))
        try:
            cli.close()
        except Exception:
            pass
        return
    except Exception as e:
        log("TLS-ERR", "%s : %r" % (host, e))
        return

    log("TLS-OK", "%s  negotiated=%s alpn=%s  <-- client accepted our cert" % (
        host, tls.version(), tls.selected_alpn_protocol()))
    try:
        req = recv_until(tls)
        if not req:
            log("EMPTY", "%s no request after handshake" % host)
            tls.close()
            return
        head, _, rest = req.partition(b"\r\n\r\n")
        lines = head.decode("utf-8", "replace").split("\r\n")
        log("REQUEST", "%s  %s" % (host, lines[0] if lines else "?"))
        for ln in lines[1:]:
            if ln:
                log("  hdr", ln)
        # body
        clen = 0
        for ln in lines[1:]:
            if ln.lower().startswith("content-length:"):
                try:
                    clen = int(ln.split(":", 1)[1].strip())
                except Exception:
                    clen = 0
        body = rest
        while len(body) < clen:
            more = tls.recv(65536)
            if not more:
                break
            body += more
        if body:
            log("  body", "%d bytes" % len(body))
            log("  body", "\n" + hexdump(body))

        path = lines[0].split(" ")[1] if lines and " " in lines[0] else "/"
        if "/api/state" in path:
            payload = fake_state(
                ARGS.servers,
                ARGS.state,
                ARGS.state_msg,
                [ARGS.catalog],
            )
            log("FAKE-STATE", "-> %s" % payload.decode("utf-8", "replace"))
            tls.sendall(http_response(payload))
        else:
            log("FAKE-OTHER", "returning empty json for %s" % path)
            tls.sendall(http_response(b"{}"))
    except Exception as e:
        log("HDL-ERR", "%s : %r" % (host, e))
    finally:
        try:
            tls.close()
        except Exception:
            pass


# ---------------------------------------------------------------- server loop
def serve(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(64)
    log("LISTEN", "0.0.0.0:%d  mode=%s" % (port, ARGS.mode))
    while True:
        try:
            cli, addr = srv.accept()
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("ACCEPT-ERR", repr(e))
            continue
        threading.Thread(target=handle_client, args=(cli, addr), daemon=True).start()


def handle_client(cli, addr):
    log("ACCEPT", "%s:%d" % addr)
    try:
        data = recv_until(cli)
        if not data:
            return
        head = data.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
        first = head.split("\r\n")[0]
        parts = first.split(" ")
        if len(parts) >= 2 and parts[0] == "CONNECT":
            hostport = parts[1]
            if ":" in hostport:
                host, port = hostport.rsplit(":", 1)
                port = int(port)
            else:
                host, port = hostport, 443
            log("CONNECT", "%s:%d" % (host, port))
            if ARGS.mode == "logonly":
                try:
                    cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                except Exception:
                    pass
                return
            if ARGS.mode == "passthrough":
                handle_http_connect_tunnel(cli, host, port)
            else:
                cli.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                handle_tls_terminated(cli, host, b"")
        else:
            # plain HTTP proxy request
            log("HTTP", first)
            log("  hdr", "\n" + hexdump(data, 1024))
            body = b'{"ok":true}'
            cli.sendall(http_response(body))
    except Exception as e:
        log("CLIENT-ERR", "%s : %r" % (addr, e))
    finally:
        try:
            cli.close()
        except Exception:
            pass


def main():
    global ARGS, LOG_FH
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["passthrough", "logonly", "tls"], default="logonly")
    ap.add_argument("--port", type=int, default=7890)
    ap.add_argument("--cert", default="certs/leaf.crt")
    ap.add_argument("--key", default="certs/leaf.key")
    ap.add_argument("--servers", default="http://127.0.0.1:5000/api/")
    ap.add_argument("--state", type=int, default=0)
    ap.add_argument("--state-msg", default="")
    ap.add_argument("--catalog", default="https://static.bluearchive-cn.com/prodm39")
    ap.add_argument("--logdir", default="logs")
    ARGS = ap.parse_args()

    # --servers may be given as comma separated list
    for name in ("servers",):
        v = getattr(ARGS, name)
        setattr(ARGS, name, [x.strip() for x in v.split(",") if x.strip()])

    os.makedirs(ARGS.logdir, exist_ok=True)
    logpath = os.path.join(ARGS.logdir, "session_%s.log" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    LOG_FH = open(logpath, "a", encoding="utf-8")

    if ARGS.mode == "tls":
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(ARGS.cert, ARGS.key)
        try:
            ctx.set_alpn_protocols(["http/1.1"])
        except Exception:
            pass
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ARGS._ctx = ctx

    log("START", "logfile=%s" % logpath)
    print("""
============================================================
 BA Prober
   mode    : %s
   port    : %d
   logfile : %s
 point the phone's Wi-Fi proxy at  <PC-IP>:%d
 (or: adb reverse tcp:%d tcp:%d, then use 127.0.0.1:%d)
============================================================
""" % (ARGS.mode, ARGS.port, logpath, ARGS.port, ARGS.port, ARGS.port, ARGS.port))
    try:
        serve(ARGS.port)
    except KeyboardInterrupt:
        pass
    log("STOP", "bye")


if __name__ == "__main__":
    main()
