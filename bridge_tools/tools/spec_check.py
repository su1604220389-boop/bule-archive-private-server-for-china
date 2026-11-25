#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验某个响应 JSON 是否符合 official_spec.json 的结构规格。

用法:
    python spec_check.py --protocol 24000 --file <response.json>
    python spec_check.py --all --outdir report\\_tmp\\official_decoded_201
    python spec_check.py --all --outdir ... --json-out result.json

判定:
    缺键        必填键(always=true)未出现          -> FAIL
    多键        spec 里没有的键                     -> FAIL
    类型不符    值与 spec 的 type 不兼容             -> FAIL
    可空性不符  null 出现在 nullable=false 的位置    -> FAIL
    数组元素    元素形状与 items 不符               -> FAIL
    可选键缺失  always=false 的键未出现              -> WARN (合法)
    长度越界    数组长度超出 len_min..len_max        -> WARN (合法但需注意)
    空数组首见  首次观测到空数组(官方样本里没有)     -> WARN
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SPEC = os.path.join(HERE, "official_spec.json")

KNUM = re.compile(r"^-?\d+$")
KSLOT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*\d{2}$")


class Report(object):
    def __init__(self):
        self.fails = []      # (kind, path, detail)
        self.warns = []

    def fail(self, kind, path, detail):
        self.fails.append((kind, path, detail))

    def warn(self, kind, path, detail):
        self.warns.append((kind, path, detail))


def jtype(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def pj(path, key=None):
    if key is None:
        return path or "$"
    if path:
        return path + "." + key
    return key


def check_value(value, spec, path, rep):
    """返回 True 表示兼容。"""
    t = spec.get("type")
    if t == "unknown":
        return True

    # ---- null / 可空性
    if value is None:
        if t == "null":
            return True
        if spec.get("nullable"):
            return True
        rep.fail("可空性不符", path, "值为 null, 但 spec type=%s nullable=false" % t)
        return False

    vt = jtype(value)

    if t == "null":
        rep.fail("类型不符", path, "spec=null, 实际=%s(%s)" % (vt, _short(value)))
        return False

    if t == "mixed":
        for i, var in enumerate(spec.get("variants") or []):
            sub = Report()
            if check_value(value, var, path, sub):
                return True
        kinds = [v.get("type") for v in (spec.get("variants") or [])]
        rep.fail("类型不符", path, "实际=%s(%s), spec=mixed%s 一种都不匹配"
                 % (vt, _short(value), kinds))
        return False

    if t == "map":
        if vt != "object":
            rep.fail("类型不符", path, "spec=map, 实际=%s(%s)" % (vt, _short(value)))
            return False
        kk = spec.get("key_kind")
        if kk == "int_str":
            bad = [k for k in value if not KNUM.match(k)]
            if bad:
                rep.fail("类型不符", path, "map<int_str> 出现非数字键 %r" % (bad[:5],))
                return False
        elif kk == "str_slot":
            bad = [k for k in value if not KSLOT.match(k)]
            if bad:
                rep.warn("键名形态", path, "map<str_slot> 出现非槽名键 %r (官方样本未出现)" % (bad[:5],))
        lo, hi = spec.get("key_count_min"), spec.get("key_count_max")
        if lo is not None and hi is not None and not (lo <= len(value) <= hi):
            rep.warn("长度越界", path, "map 键数 %d 不在观测范围 [%s,%s]" % (len(value), lo, hi))
        valspec = spec.get("value")
        if valspec:
            for k, v in value.items():
                check_value(v, valspec, pj(path, k), rep)
        return True

    if t == "object":
        if vt != "object":
            rep.fail("类型不符", path, "spec=object, 实际=%s(%s)" % (vt, _short(value)))
            return False
        fields = spec.get("fields") or {}
        if spec.get("observed_empty_only") and value:
            rep.fail("形状未知", path, "spec: 官方样本里此节点始终是空对象, 而这里有 %d 个键 %r"
                     % (len(value), sorted(value)[:5]))
            return False
        ok = True
        for k, fs in fields.items():
            if k not in value:
                denom = fs.get("parent_instances", fs.get("of"))
                if fs.get("always"):
                    rep.fail("缺键", pj(path, k), "必填键缺失 (官方观测 seen=%s/%s)"
                             % (fs.get("seen"), denom))
                    ok = False
                else:
                    rep.warn("可选键缺失", pj(path, k), "always=false 未出现 (官方观测 %s/%s 次有)"
                             % (fs.get("seen"), denom))
            else:
                if not check_value(value[k], fs, pj(path, k), rep):
                    ok = False
        for k in value:
            if k not in fields:
                rep.fail("多键", pj(path, k), "spec 中不存在该键 (值类型 %s)" % jtype(value[k]))
                ok = False
        return ok

    if t in ("int", "float", "number", "str", "bool"):
        if t == "int":
            if vt != "int":
                rep.fail("类型不符", path, "spec=int, 实际=%s(%s)" % (vt, _short(value)))
                return False
            return True
        if t == "float":
            if vt == "float":
                return True
            if vt == "int":
                rep.warn("类型不符", path, "spec=float, 实际=int(%s) (proto3 JSON 会把 0.0 写成 0)" % _short(value))
                return True
            rep.fail("类型不符", path, "spec=float, 实际=%s(%s)" % (vt, _short(value)))
            return False
        if t == "number":
            if vt in ("int", "float"):
                return True
            rep.fail("类型不符", path, "spec=number, 实际=%s(%s)" % (vt, _short(value)))
            return False
        if t == "str":
            if vt != "str":
                rep.fail("类型不符", path, "spec=str, 实际=%s(%s)" % (vt, _short(value)))
                return False
            return True
        if t == "bool":
            if vt != "bool":
                rep.fail("类型不符", path, "spec=bool, 实际=%s(%s)" % (vt, _short(value)))
                return False
            return True

    if t == "array":
        return check_array(value, spec, path, rep)

    rep.fail("类型不符", path, "spec 中未知 type=%r" % (t,))
    return False


def _short(v, limit=40):
    try:
        s = json.dumps(v, ensure_ascii=False)
    except Exception:
        s = repr(v)
    return s if len(s) <= limit else s[:limit] + "..."


def _type_compatible(value, spec):
    """只判断本条值自身的类型类别是否与 spec 兼容(不递归, 不报错)。"""
    t = spec.get("type")
    if t in ("unknown", "mixed"):
        return True
    if value is None:
        return t == "null" or bool(spec.get("nullable"))
    vt = jtype(value)
    if t == "null":
        return False
    if t in ("object", "map"):
        return vt == "object"
    if t == "array":
        return vt == "array"
    if t == "int":
        return vt == "int"
    if t == "float":
        return vt in ("float", "int")
    if t == "number":
        return vt in ("int", "float")
    if t in ("str", "bool"):
        return vt == t
    return True


def check_array(value, spec, path, rep):
    if spec.get("type") != "array":
        return check_value(value, spec, path, rep)
    if not isinstance(value, list):
        return check_value(value, spec, path, rep)
    lo, hi = spec.get("len_min"), spec.get("len_max")
    if lo is not None and hi is not None and not (lo <= len(value) <= hi):
        rep.warn("长度越界", path, "数组长度 %d 不在观测范围 [%s,%s]" % (len(value), lo, hi))
    if not value and spec.get("empty_observations") == 0:
        rep.warn("空数组首见", path, "官方样本中未出现空数组")
    item = spec.get("items")
    if not item or item.get("type") == "unknown":
        return True
    ok = True
    for i, el in enumerate(value):
        p = "%s[%d]" % (path, i)
        if not _type_compatible(el, item):
            rep.fail("数组元素形状不符", p, "spec.items=%s%s, 实际=%s(%s)"
                     % (item.get("type"),
                        "" if item.get("type") != "map" else "(map)",
                        jtype(el), _short(el)))
            ok = False
            continue
        if not check_value(el, item, p, rep):
            ok = False
    return ok


def check_root(value, spec, path, rep):
    """根节点/任意节点统一入口: array 需要单独处理长度信息。"""
    if spec.get("type") == "array":
        return check_array(value, spec, path, rep)
    return check_value(value, spec, path, rep)


# ---------------------------------------------------------------- 文件处理
def load_response(path):
    with open(path, "r", encoding="utf-8") as fh:
        j = json.load(fh)
    if isinstance(j, dict) and "inner" in j:
        return j["inner"], j
    if isinstance(j, dict) and "Protocol" in j:
        return j, {}
    raise SystemExit("无法识别的响应文件: " + path)


def check_one(proto, inner, spec, src):
    entry = spec["protocols"].get(str(proto))
    if entry is None:
        rep = Report()
        rep.fail("协议不存在", "$", "spec 中没有协议 %s" % (proto,))
        return rep, entry
    rep = Report()
    check_root(inner, entry["schema"], "", rep)
    return rep, entry


def main(argv=None):
    ap = argparse.ArgumentParser(description="用 official_spec.json 校验响应 JSON 的结构")
    ap.add_argument("--protocol", type=str, help="协议号, 例如 24000")
    ap.add_argument("--file", help="单个响应 json")
    ap.add_argument("--all", action="store_true", help="批量校验一个目录")
    ap.add_argument("--outdir", help="批量校验的目录")
    ap.add_argument("--spec", default=DEFAULT_SPEC, help="spec 路径")
    ap.add_argument("--json-out", help="把汇总写到此 json")
    ap.add_argument("--max-detail", type=int, default=40, help="每个文件最多打印的差异条数")
    args = ap.parse_args(argv)

    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)

    if args.all:
        outdir = args.outdir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
            "report", "_tmp", "official_decoded_201")
        files = sorted(glob.glob(os.path.join(outdir, "*.response.json")))
        if not files:
            raise SystemExit("目录里没有 *.response.json: " + outdir)
        per_proto = OrderedDict()
        total_fail = 0
        total_files = 0
        for f in files:
            inner, wrapper = load_response(f)
            proto = inner.get("Protocol")
            if proto is None:
                print("SKIP (无 Protocol): %s" % f)
                continue
            rep, entry = check_one(proto, inner, spec, f)
            total_files += 1
            agg = per_proto.setdefault(str(proto), {
                "name": entry["name"] if entry else "?",
                "files": 0, "pass": 0, "fail": 0,
                "fails": [], "warns": 0, "spec_observations": entry["observations"] if entry else 0,
            })
            agg["files"] += 1
            agg["warns"] += len(rep.warns)
            if rep.fails:
                total_fail += 1
                agg["fail"] += 1
                agg["fails"].append({"file": os.path.basename(f),
                                     "errors": [{"kind": k, "path": p, "detail": d}
                                                for k, p, d in rep.fails]})
                print("FAIL %-8s %s  (%d 处差异)"
                      % (proto, os.path.basename(f), len(rep.fails)))
                for k, p, d in rep.fails[:args.max_detail]:
                    print("    - [%s] %s  %s" % (k, p, d))
                if len(rep.fails) > args.max_detail:
                    print("    ... 还有 %d 条" % (len(rep.fails) - args.max_detail))
            else:
                agg["pass"] += 1
                print("PASS %-8s %s%s"
                      % (proto, os.path.basename(f),
                         "" if not rep.warns else "  (warn %d)" % len(rep.warns)))

        print("")
        print("=" * 78)
        print("协议  名称                            文件  PASS  FAIL  spec观测  WARN")
        def _pkey(x):
            return (0, int(x)) if str(x).isdigit() else (1, str(x))
        for p in sorted(per_proto, key=_pkey):
            a = per_proto[p]
            print("%-6s %-30s %4d %5d %5d %8d %5d"
                  % (p, a["name"][:30], a["files"], a["pass"], a["fail"],
                     a["spec_observations"], a["warns"]))
        print("-" * 78)
        print("总计: 文件 %d, PASS %d, FAIL %d, 协议 %d"
              % (total_files, total_files - total_fail, total_fail, len(per_proto)))
        print("结论: %s" % ("PASS" if total_fail == 0 else "FAIL"))
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"total_files": total_files,
                           "pass": total_files - total_fail, "fail": total_fail,
                           "protocols": per_proto}, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        return 0 if total_fail == 0 else 1

    # ---- 单文件模式
    if not args.file:
        ap.error("要么给 --all --outdir, 要么给 --protocol N --file F")
    inner, wrapper = load_response(args.file)
    proto = inner.get("Protocol")
    if args.protocol and str(args.protocol) != str(proto):
        print("FAIL  协议不符: --protocol=%s, 文件内 Protocol=%s" % (args.protocol, proto))
        return 1
    rep, entry = check_one(proto, inner, spec, args.file)
    print("协议 %s (%s)  文件 %s" % (proto, entry["name"] if entry else "?",
                                    os.path.basename(args.file)))
    print("spec 观测次数: %s" % (entry["observations"] if entry else "?"))
    for k, p, d in rep.fails:
        print("  FAIL [%s] %s  %s" % (k, p, d))
    for k, p, d in rep.warns:
        print("  WARN [%s] %s  %s" % (k, p, d))
    print("结果: %s  (差异 %d 条, 提示 %d 条)"
          % ("PASS" if not rep.fails else "FAIL", len(rep.fails), len(rep.warns)))
    return 0 if not rep.fails else 1


if __name__ == "__main__":
    sys.exit(main())
