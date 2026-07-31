#!/usr/bin/env python3
"""Score one translation unit with objdiff, non-interactively.

`objdiff-cli diff` needs a TTY and refuses to run headless ("No such device or address"),
and `objdiff-cli report generate` over the whole project aborts on the 76 degenerate PHONY
stub objects (see ../halo-report.sh). Neither is usable from an agent or a script.

This writes a temporary objdiff.json containing only the requested units, runs `report
generate` against it, and prints per-function match percentages. Nothing is mutated: the real
objdiff.json is left alone.

    python3 tools/score_unit.py source/math/random_math
    python3 tools/score_unit.py source/math/random_math --functions
    python3 tools/score_unit.py --all-in source/math

Assumes the candidate object already exists — run `ninja` first (or
`ninja build/base/<unit>.obj` to compile just one).
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJDIFF = ROOT / "objdiff.json"
CLI = ROOT / "build" / "tools" / "objdiff-cli"


def _f(d: dict, key: str) -> float:
    """Report numbers arrive as either floats or decimal strings depending on the field."""
    try:
        return float(d.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def load_units() -> list[dict]:
    return json.loads(OBJDIFF.read_text()).get("units", [])


def is_stub(unit: dict) -> bool:
    """PHONY stubs have invalid COFF symbol tables and abort objdiff-cli outright."""
    tp = unit.get("target_path")
    if not tp:
        return False
    p = ROOT / tp
    return p.exists() and b"PHONY" in p.read_bytes()[:512]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("units", nargs="*", help="unit names, e.g. source/math/random_math")
    ap.add_argument("--all-in", metavar="DIR", help="score every unit under this directory")
    ap.add_argument("--functions", action="store_true", help="list per-function percentages")
    ap.add_argument("--objdiff", metavar="PATH", default=str(CLI),
                    help="objdiff-cli binary to use (default: pinned %(default)s)")
    ap.add_argument("-c", "--config", metavar="KEY=VALUE", action="append", default=[],
                    help="objdiff config property, passed through to `report generate -c`, "
                         "e.g. -c functionRelocDiffs=name_check (requires objdiff >= 4.x fork; "
                         "the pinned 3.3.1 has no name_check variant)")
    args = ap.parse_args()

    cfg = json.loads(OBJDIFF.read_text())
    all_units = cfg.get("units", [])

    if args.all_in:
        want = [u for u in all_units if u["name"].startswith(args.all_in.rstrip("/") + "/")]
    else:
        names = set(args.units)
        want = [u for u in all_units if u["name"] in names]
        missing = names - {u["name"] for u in want}
        if missing:
            sys.exit(f"no such unit(s): {', '.join(sorted(missing))}")
    if not want:
        sys.exit("no units selected")

    skipped = [u["name"] for u in want if is_stub(u)]
    want = [u for u in want if not is_stub(u)]
    for n in skipped:
        print(f"skip {n}: PHONY stub (no section contribution — see tools/reccmp/README.md)")
    if not want:
        return 1

    # Units with no base_path at all (not yet decompiled) can't be scored; drop them
    # silently in --all-in mode rather than crashing on the missing key.
    want = [u for u in want if u.get("base_path")]
    if not want:
        sys.exit("no scoreable units selected (none have a base_path)")
    missing_base = [u["name"] for u in want if not (ROOT / u["base_path"]).exists()]
    if missing_base:
        print("candidate object not built for: " + ", ".join(missing_base), file=sys.stderr)
        print("run `ninja` first", file=sys.stderr)
        return 1

    cfg["units"] = want
    # Build a throwaway project directory that symlinks back to the real build outputs and
    # carries its own filtered objdiff.json. This deliberately avoids mutating the repo's
    # objdiff.json even briefly — several agents score concurrently, and an in-place swap
    # would race and could leave the file truncated.
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        for entry in ("build", "source", "libs", "config"):
            src = ROOT / entry
            if src.exists():
                (proj / entry).symlink_to(src)
        (proj / "objdiff.json").write_text(json.dumps(cfg))
        out = proj / "report.json"
        cmd = [args.objdiff, "report", "generate", "-p", str(proj), "-o", str(out)]
        for kv in args.config:
            cmd += ["-c", kv]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
            return proc.returncode
        report = json.loads(out.read_text())

    for unit in report.get("units", []):
        m = unit.get("measures", {})
        print(f"\n{unit['name']}")
        # matched_code_percent is the EXACT-byte metric: a function contributes 0 unless it
        # is byte-identical. fuzzy_match_percent is the graded one. A unit can sit at 99.9%
        # fuzzy and still report a much lower exact percent — that is correct, not a bug.
        print(f"  code   {_f(m, 'matched_code_percent'):6.2f}% exact   "
              f"({m.get('matched_code', 0)}/{m.get('total_code', 0)} bytes)"
              f"   fuzzy {_f(m, 'fuzzy_match_percent'):6.2f}%")
        print(f"  data   {_f(m, 'matched_data_percent'):6.2f}% exact   "
              f"({m.get('matched_data', 0)}/{m.get('total_data', 0)} bytes)")
        print(f"  funcs  {m.get('matched_functions', 0)}/{m.get('total_functions', 0)}")
        # Section fuzzy percentages matter for data-only units: a tag table can sit at 93%
        # fuzzy while `matched_data` is absent entirely (i.e. zero bytes match exactly), and
        # showing only the unit-level number makes that look like 0% progress.
        for sec in unit.get("sections", []):
            print(f"    section {sec.get('name', '?'):<10} {sec.get('size', 0):>7} bytes"
                  f"   fuzzy {_f(sec, 'fuzzy_match_percent'):7.3f}%")
        if args.functions:
            # Functions carry `fuzzy_match_percent` and `size` directly — there is no
            # per-function `measures` dict, which an earlier version of this script assumed
            # and so reported 0.00%/0 bytes for everything.
            for fn in sorted(unit.get("functions", []),
                             key=lambda f: _f(f, "fuzzy_match_percent")):
                pct = _f(fn, "fuzzy_match_percent")
                flag = "OK " if pct >= 100 else "-- "
                print(f"    {flag}{pct:7.3f}%  {fn.get('name', '?')}"
                      f"  ({fn.get('size', 0)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
