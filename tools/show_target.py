#!/usr/bin/env python3
"""Show the target object's disassembly, relocations and symbols for a unit.

For matching work this is the primary source of truth, ahead of any decompiler. The objects
under `build/split/` were carved out of `cachebeta.exe` by csplit using the original PDB, so
they carry real symbol names and COFF relocations — `objdump -d -r` resolves every call target
to its actual name. That is strictly better evidence than a decompiler's reconstruction, which
can introduce control-flow and type noise of its own.

Ghidra still earns its place for breadth — 7,840 PDB-applied names, cross-references, "what does
this callback actually do" — but for the per-unit matching loop, start here.

    python3 tools/show_target.py source/text/font_group            # disassembly + relocs
    python3 tools/show_target.py source/text/font_group --symbols  # symbol table
    python3 tools/show_target.py source/text/font_group --data     # data section hexdump
    python3 tools/show_target.py source/text/font_group --base     # OUR object, to compare

Requires binutils' i686 PE objdump (`i686-w64-mingw32-objdump`, package `mingw-w64-binutils`).
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJDUMP = "i686-w64-mingw32-objdump"


def find_unit(name: str) -> dict:
    cfg = json.loads((ROOT / "objdiff.json").read_text())
    for unit in cfg.get("units", []):
        if unit["name"] == name:
            return unit
    sys.exit(f"no such unit: {name}")


def run(args: list[str]) -> int:
    proc = subprocess.run([OBJDUMP, *args], check=False)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("unit", help="unit name, e.g. source/text/font_group")
    ap.add_argument("--symbols", action="store_true", help="symbol table instead of disassembly")
    ap.add_argument("--data", action="store_true", help="hexdump the data sections")
    ap.add_argument("--headers", action="store_true", help="section headers")
    ap.add_argument("--base", action="store_true",
                    help="show OUR compiled object rather than the target")
    args = ap.parse_args()

    if not shutil.which(OBJDUMP):
        sys.exit(f"{OBJDUMP} not found — install mingw-w64-binutils")

    unit = find_unit(args.unit)
    key = "base_path" if args.base else "target_path"
    obj = ROOT / unit[key]
    if not obj.exists():
        hint = "run `ninja` first" if args.base else "run `configure.py` to csplit the baserom"
        sys.exit(f"{obj} does not exist — {hint}")

    if args.symbols:
        return run(["-t", str(obj)])
    if args.headers:
        return run(["-h", str(obj)])
    if args.data:
        # -s dumps full section contents; restrict to the data sections since .text is
        # better read as disassembly.
        rc = 0
        for sec in (".data", ".rdata", ".bss"):
            rc |= run(["-s", "-j", sec, str(obj)])
        return rc
    # -r interleaves relocations, which is what turns anonymous `call` targets into names.
    return run(["-d", "-r", "-M", "intel", str(obj)])


if __name__ == "__main__":
    raise SystemExit(main())
