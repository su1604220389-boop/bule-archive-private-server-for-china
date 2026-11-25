#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p4_proxy.py -- P4 判定用 TLS 终止代理（DD3 配套）
=================================================
用途：判定 "客户端到底认不认我们装在【用户证书】里的 CA"。
      同时支持两种重定向方式：

  A) 代理模式（免 root，首选）
     python p4_proxy.py --mode proxy --port 7890 \
         --cert ca_leaf.crt --key ca_leaf.key \
         --mitm "state-api|stateqc-api|gsqc-api|gs-api" --pass-others

     手机 Wi-Fi 代理指向 <PC-IP>:7890。匹配 --mitm 的主机被本地 TLS 终止；
     不匹配的主机（SDK / udata / ACE / 公告 …）用 --pass-others 原样隧道到真服务器，
     避免"SDK 初始化失败导致游戏压根走不到 state"这种混淆变量。

  B) 直连模式（配 DNAT，需要 root 做重定向）
     python p4_proxy.py --mode direct --port 443 --cert ... --key ...

     手机 iptables DNAT 把 *:443 指到本机 443；没有 CONNECT，
     直接用 SNI 回调拿到主机名。

判据输出（一行一个结论，便于 grep）：
  P4-CONNECT   <host:port>                     客户端来连了（重定向成立）
  P4-TLS-OK    <host> ver=... alpn=...         客户端【接受】了我们的证书  ← 信任成立
  P4-TLS-REJECT <host> alert=<reason>          客户端【拒绝】了我们的证书  ← 信任不成立
  P4-REQ       <host> <method> <path>          握手过了之后真的发了请求
  P4-SUMMARY   ...                             退出时汇总（Ctrl-C）

没有第三方依赖（纯 stdlib）。日志同时写 <logdir>/p4_<ts>.log 和 <logdir>/p4_<ts>.json。

注意：本文件未做联网自测（本次任务禁止联网），只做了 py_compile 语法校验；
      它是 work/ba/.../BA_probe_kit_v1/pc/state_gw.py 的同源派生，
      那条 TLS 终止 + CONNECT 主路径在项目里已跑过（BA_probe_kit_v1 的 E4）。
"""

import argparse
import json
import os
import re
import socket
import ssl
import struct
import sys
import threading
import time
from datetime import datetime

ARGS = None
LOCK = threading.Lock()
LOG_FH = None
RESULTS = []          # [(kind, host, detail)]
COUNTS = {"connect": 0, "tls_ok": 0, "tls_reject": 0, "req": 0, "passthrough": 0}


# ------------------------------------------------------------------ logging
def log(tag, msg):
    line = "[%s] %-13s %s" % (datetime.now().strftime("%H:%M:%S.%f")[:-3], tag, msg)
    with LOCK:
        print(line, flush=True)
        if LOG_FH:
            LOG_FH.write(line + "\n")
            LOG_FH.flush()


def record(kind, host, detail=""):
    with LOCK:
        RESULTS.append({"kind": kind, "host": host, "detail": detail,
                        "t": datetime.now().isoformat(timespec="milliseconds")})
        if kind in COUNTS:
            COUNTS[kind] += 1


# ------------------------------------------------- TLS ClientHello SNI 解析
def parse_sni(buf):
    """从 ClientHello 里取 SNI。失败返回 None，绝不抛异常。"""
    try:
        if len(buf) < 5 or buf[0] != 0x16:
            return None
        rec_len = struct.unpack(">H", buf[3:5])[0]
        body = buf[5:5 + rec_len]
        if len(body) < 4 or body[0] != 0x01:
            return None
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
            if etype == 0 and len(data) >= 5:
                nlen = struct.unpack(">H", data[3:5])[0]
                return data[5:5 + nlen].decode("ascii", "replace")
        return None
    except Exception:
        return None


def peek(sock, timeout=4.0, n=4096):
    sock.settimeout(timeout)
    try:
        b = sock.recv(n, socket.MSG_PEEK)
    except Exception:
        return b""
    return b


def recv_until_headers(sock, maxb=65536):
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < maxb:
        try:
            chunk = sock.recv(4096)
        except Exception:
            break
        if not chunk:
            break
        buf += chunk
    return buf


# ------------------------------------------------------------ 透传（不 MITM）
def passthrough(cli, host, port):
    try:
        up = socket.create_connection((host, port), timeout=10)
    except Exception as e:
        log("PASS-FAIL", "%s:%s %r" % (host, port, e))
        try:
            cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
        except Exception:
            pass
        return
    try:
        cli.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
    except Exception:
        pass
    log("P4-PASS", "%s:%s tunneled (not MITM)" % (host, port))
    record("passthrough", host, "%s" % port)

    def one(src, dst):
        try:
            while True:
                d = src.recv(65536)
                if not d:
                    break
                dst.sendall(d)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    t = threading.Thread(target=one, args=(up, cli), daemon=True)
    t.start()
    one(cli, up)
    t.join(timeout=60)
    try:
        up.close()
    except Exception:
        pass


# --------------------------------------------------------------- MITM 终止
def http_resp(body, code="200 OK", ctype="application/json"):
    head = ("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Connection: close\r\n\r\n" % (code, ctype, len(body)))
    return head.encode("ascii") + body


def fake_state(servers, state, msg, catalog):
    return json.dumps({
        "Servers": servers,
        "State": state,
        "Msg": msg,
        "CallbackUrl": "",
        "CustomerServiceUrl": "",
        "AddressablesCatalogUrlRoots": catalog,
    }, ensure_ascii=False).encode("utf-8")


def classify_ssl_error(e):
    """把 Python 的 SSLError 归类成能直接对上 TLS alert 表的字符串。"""
    s = str(e).lower()
    for key in ("unknown ca", "unknown_ca", "bad certificate", "certificate unknown",
                "access denied", "handshake failure", "no application protocol",
                "unsupported protocol", "tlsv1 alert", "wrong version number"):
        if key in s:
            return key
    return str(e)[:160]


def finish_tls(tls, host):
    """握手成功后的 HTTP 处理。"""
    req = recv_until_headers(tls)
    if not req:
        log("P4-EMPTY", "%s TLS ok but no HTTP request" % host)
        return
    head, _, rest = req.partition(b"\r\n\r\n")
    lines = head.decode("utf-8", "replace").split("\r\n")
    first = lines[0] if lines else "?"
    log("P4-REQ", "%s  %s" % (host, first))
    record("req", host, first)
    try:
        path = first.split(" ")[1]
    except Exception:
        path = "/"
    if "/api/state" in path:
        body = fake_state(ARGS.servers, ARGS.state, ARGS.state_msg, [ARGS.catalog])
        log("P4-FAKE", "state -> %s" % body.decode("utf-8", "replace"))
        tls.sendall(http_resp(body))
    else:
        log("P4-FAKE", "%s -> {} (keep client running)" % path)
        tls.sendall(http_resp(b"{}"))


def mitm(cli, host):
    ctx = ARGS._ctx
    # 一旦 wrap_socket 成功 = 客户端接受了我们的证书；抛 SSLError = 客户端拒绝
    try:
        tls = ctx.wrap_socket(cli, server_side=True)
    except ssl.SSLError as e:
        reason = classify_ssl_error(e)
        log("P4-TLS-REJECT", "%s alert=%s  <== CLIENT REJECTED OUR CERT" % (host, reason))
        record("tls_reject", host, reason)
        try:
            cli.close()
        except Exception:
            pass
        return
    except Exception as e:
        log("P4-TLS-ERR", "%s %r" % (host, e))
        return
    try:
        alpn = tls.selected_alpn_protocol()
    except Exception:
        alpn = None
    log("P4-TLS-OK", "%s ver=%s alpn=%s  <== CLIENT ACCEPTED OUR CERT" %
        (host, getattr(tls, "version", lambda: "?")() if callable(getattr(tls, "version", None)) else "?", alpn))
    record("tls_ok", host, "alpn=%s" % alpn)
    try:
        finish_tls(tls, host)
    except Exception as e:
        log("P4-HDLERR", "%s %r" % (host, e))
    finally:
        try:
            tls.close()
        except Exception:
            pass


# --------------------------------------------------------------- 连接处理
def handle_proxy(cli, addr):
    data = recv_until_headers(cli)
    if not data:
        return
    head = data.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
    first = head.split("\r\n")[0]
    parts = first.split(" ")
    if len(parts) >= 2 and parts[0].upper() == "CONNECT":
        hostport = parts[1]
        if ":" in hostport:
            host, port = hostport.rsplit(":", 1)
            port = int(port)
        else:
            host, port = hostport, 443
        log("P4-CONNECT", "%s:%d" % (host, port))
        record("connect", host, str(port))
        if port != 443 and not ARGS.mitm_any:
            passthrough(cli, host, port)
            return
        if ARGS.mitm_re.search(host):
            try:
                cli.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            except Exception:
                return
            mitm(cli, host)
        elif ARGS.pass_others:
            passthrough(cli, host, port)
        else:
            log("P4-SKIP", "%s not in --mitm and --pass-others off -> 502" % host)
            try:
                cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except Exception:
                pass
    else:
        log("P4-HTTP", "plain http request: %s" % first)
        try:
            cli.sendall(http_resp(b'{"ok":true}'))
        except Exception:
            pass


def handle_direct(cli, addr):
    """DNAT 模式：连接直接就是 TLS，主机名只能从 ClientHello 里取。"""
    hello = peek(cli, timeout=4.0)
    host = parse_sni(hello) or "<no-sni>"
    log("P4-CONNECT", "%s (direct, sni=%s)" % (addr[0], host))
    record("connect", host, "direct")
    mitm(cli, host)


def serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((ARGS.bind, ARGS.port))
    srv.listen(64)
    log("P4-LISTEN", "%s:%d mode=%s mitm=%s pass_others=%s" %
        (ARGS.bind, ARGS.port, ARGS.mode, ARGS.mitm, ARGS.pass_others))
    while True:
        try:
            cli, addr = srv.accept()
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("P4-ACCEPT-ERR", repr(e))
            continue
        fn = handle_proxy if ARGS.mode == "proxy" else handle_direct
        threading.Thread(target=fn, args=(cli, addr), daemon=True).start()


# ------------------------------------------------------------------- 收尾
def summary(path):
    ok = sorted({r["host"] for r in RESULTS if r["kind"] == "tls_ok"})
    rej = sorted({r["host"] for r in RESULTS if r["kind"] == "tls_reject"})
    con = sorted({r["host"] for r in RESULTS if r["kind"] == "connect"})
    log("P4-SUMMARY", "connect=%d tls_ok=%d tls_reject=%d req=%d pass=%d" %
        (COUNTS["connect"], COUNTS["tls_ok"], COUNTS["tls_reject"],
         COUNTS["req"], COUNTS["passthrough"]))
    log("P4-SUMMARY", "connect hosts : %s" % (", ".join(con) or "-"))
    log("P4-SUMMARY", "TLS accepted  : %s" % (", ".join(ok) or "-"))
    log("P4-SUMMARY", "TLS rejected  : %s" % (", ".join(rej) or "-"))
    if ok and not rej:
        log("P4-VERDICT", "A = USER-STORE CA ACCEPTED (at least one host accepted our cert)")
    elif rej and not ok:
        log("P4-VERDICT", "B = USER-STORE CA NOT ACCEPTED (all rejected)")
    elif ok and rej:
        log("P4-VERDICT", "C = MIXED: some hosts accept, some reject (likely two TLS stacks)")
    elif not con:
        log("P4-VERDICT", "D = NO CONNECT: redirection failed, not a trust question")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"counts": COUNTS, "events": RESULTS,
                   "accepted": ok, "rejected": rej, "connected": con},
                  f, ensure_ascii=False, indent=2)


def main():
    global ARGS, LOG_FH
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["proxy", "direct"], default="proxy")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=7890)
    ap.add_argument("--cert", required=True, help="leaf.crt (PEM, 含完整链更好)")
    ap.add_argument("--key", required=True, help="leaf.key")
    ap.add_argument("--mitm", default=r"state-api|stateqc-api|gsqc-api|gs-api|bluearchive-cn\.com",
                    help="要 MITM 的主机正则")
    ap.add_argument("--pass-others", action="store_true",
                    help="不匹配 --mitm 的主机原样隧道到真服务器（避免 SDK 段被打断）")
    ap.add_argument("--mitm-any", action="store_true", help="所有 CONNECT 都 MITM（不看端口）")
    ap.add_argument("--servers", default="http://127.0.0.1:5000/api/",
                    help="假 /api/state 里的 Servers 数组，逗号分隔；用 http:// 是为了让后续链路走明文")
    ap.add_argument("--state", type=int, default=0)
    ap.add_argument("--state-msg", default="")
    ap.add_argument("--catalog", default="https://static.bluearchive-cn.com/prodm39")
    ap.add_argument("--logdir", default="p4logs")
    ARGS = ap.parse_args()

    ARGS.servers = [x.strip() for x in ARGS.servers.split(",") if x.strip()]
    ARGS.mitm_re = re.compile(ARGS.mitm)

    os.makedirs(ARGS.logdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt = os.path.join(ARGS.logdir, "p4_%s.log" % stamp)
    js = os.path.join(ARGS.logdir, "p4_%s.json" % stamp)
    LOG_FH = open(txt, "a", encoding="utf-8")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ARGS.cert, ARGS.key)
    try:
        ctx.set_alpn_protocols(["http/1.1"])
    except Exception:
        pass
    # 我们只是**服务端**：不校验证书（要验证的是客户端，不是我们）
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ARGS._ctx = ctx

    log("P4-START", "log=%s json=%s" % (txt, js))
    log("P4-START", "cert=%s" % ARGS.cert)
    print("""
================================================================
 P4 判定器
   mode        : %s      port: %d      bind: %s
   MITM 主机   : %s
   pass others : %s
   假 state    : Servers=%s State=%d
 手机侧：Wi-Fi 代理 -> <PC-IP>:%d（或 DNAT 到 %d）
 判据：P4-TLS-OK = 客户端接受我们的证书；P4-TLS-REJECT = 拒绝
================================================================
""" % (ARGS.mode, ARGS.port, ARGS.bind, ARGS.mitm, ARGS.pass_others,
       ARGS.servers, ARGS.state, ARGS.port, ARGS.port))

    try:
        serve()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            summary(js)
        except Exception as e:
            log("P4-SUMERR", repr(e))


if __name__ == "__main__":
    main()
