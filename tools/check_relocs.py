#!/usr/bin/env python3
"""Compare external relocation symbol names between our object and the target.

**objdiff does not check these.** Verified destructively: renaming a callee to
`_object_get_and_verify_typeX` in a matching unit still scores 100.00% exact, because the
scorer compares instruction bytes and relocation *slots*, not the symbol names those
relocations point at. A `call` is five bytes of `e8 00 00 00 00` plus a relocation record
either way.

So "the unit is at 100%" does not mean the callee names are right, and a wrong name is a real
defect: it will not link, and it silently misrepresents which function the original called. One
such defect was already found by hand in source/cache/predicted_resources (external names were
missing their leading underscore).

    python3 tools/check_relocs.py source/sound/sound_scenery
    python3 tools/check_relocs.py --all          # every unit whose candidate object exists

Exit status is 1 if any mismatch is found, so this is usable as a CI gate.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJDUMP = "i686-w64-mingw32-objdump"

# objdump -d -r prints relocations as an indented line under the instruction they patch:
#     1a: DISP32  _tag_block_get_element_with_size
# Instruction lines have the same leading "<hex>:" shape ("   0: 55  push ebp"), so the
# relocation TYPE must be matched against a known set — otherwise mnemonics like `push` and
# `nop` are scraped as if they were symbol names.
RELOC_TYPES = {
    "DISP32", "dir32", "DIR32", "dir32nb", "secrel32", "secidx", "IMAGE_REL_I386_DIR32",
    "IMAGE_REL_I386_REL32", "rva32", "disp32",
}
RELOC_RE = re.compile(r"^\s+[0-9a-f]+:\s+(\S+)\s+(\S+)\s*$")

# csplit synthesises placeholder names for target symbols the PDB had no public name for.
# They are expected to differ from ours and are not defects.
PLACEHOLDER_RE = re.compile(r"^_?(data|code|bss|rdata)_[0-9a-f]{6,}$")

# MSVC-internal names that carry no cross-unit meaning: `$L2437` jump-table and block labels,
# and `__real@...` / `__xmm@...` COMDAT floating-point literals, which the linker folds and
# which each object names for itself.
INTERNAL_RE = re.compile(r"^(\$|__real@|__xmm@|\.)")

# objdump appends an addend to the symbol when the relocation targets an offset into it, e.g.
# `_object_list_data-0x4`. That is the same symbol, so strip it before comparing.
ADDEND_RE = re.compile(r"[+-]0x[0-9a-f]+$")


def relocs(obj: Path) -> tuple[Counter, int]:
    """(multiset of real relocation target names, count of csplit placeholder relocations).

    Placeholders are separated out because the target legitimately carries them wherever the
    PDB had no public name for a static — we supply a real name there, and that substitution
    is the goal, not a defect.
    """
    out = subprocess.run([OBJDUMP, "-d", "-r", str(obj)],
                         capture_output=True, text=True, check=False).stdout
    names, placeholders = Counter(), 0
    for line in out.splitlines():
        m = RELOC_RE.match(line)
        if not m or m.group(1) not in RELOC_TYPES:
            continue
        sym = ADDEND_RE.sub("", m.group(2))
        if INTERNAL_RE.match(sym):
            continue
        if PLACEHOLDER_RE.match(sym):
            placeholders += 1
        else:
            names[sym] += 1
    return names, placeholders


_REPORT: dict[str, float] = {}


def _fuzzy(name: str) -> float:
    """Per-unit fuzzy percentage, from one cached whole-project objdiff report."""
    if not _REPORT:
        import tempfile
        cfg = json.loads((ROOT / "objdiff.json").read_text())
        cfg["units"] = [u for u in cfg.get("units", [])
                        if u.get("target_path") and (ROOT / u["target_path"]).exists()
                        and b"PHONY" not in (ROOT / u["target_path"]).read_bytes()[:512]]
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            for entry in ("build", "source", "libs", "config"):
                if (ROOT / entry).exists():
                    (proj / entry).symlink_to((ROOT / entry).resolve())
            (proj / "objdiff.json").write_text(json.dumps(cfg))
            out = proj / "report.json"
            subprocess.run([str(ROOT / "build" / "tools" / "objdiff-cli"), "report", "generate",
                            "-p", str(proj), "-o", str(out)],
                           capture_output=True, text=True, check=False)
            for u in json.loads(out.read_text()).get("units", []):
                try:
                    _REPORT[u["name"]] = float(u["measures"].get("fuzzy_match_percent", 0) or 0)
                except (TypeError, ValueError):
                    _REPORT[u["name"]] = 0.0
    return _REPORT.get(name, 0.0)


def check(unit: dict, verbose: bool) -> bool:
    """True if the unit's external relocation names agree with the target."""
    # Some units (PHONY stubs, units with no candidate) carry no base_path at all.
    if not unit.get("base_path") or not unit.get("target_path"):
        return True
    base, target = ROOT / unit["base_path"], ROOT / unit["target_path"]
    if not base.exists() or not target.exists():
        return True
    if b"PHONY" in target.read_bytes()[:512]:
        return True

    ours, ours_ph = relocs(base)
    theirs, theirs_ph = relocs(target)

    missing = theirs - ours          # target references a name we never emit — a real defect
    extra = ours - theirs            # we reference a name the target does not
    # Names we emit where the target had a placeholder are the expected substitution. Only
    # flag extras beyond the number of placeholders the target actually carries.
    unexplained_extra = max(0, sum(extra.values()) - theirs_ph)

    if not missing and not unexplained_extra:
        if verbose:
            print(f"ok   {unit['name']}  ({sum(ours.values())} named relocs, "
                  f"{theirs_ph} target placeholders named by us)")
        return True

    print(f"MISMATCH  {unit['name']}")
    for n, c in sorted(missing.items()):
        print(f"    target references, we do not:  {n}" + (f" (x{c})" if c > 1 else ""))
    if unexplained_extra:
        for n, c in sorted(extra.items()):
            print(f"    we reference, target does not: {n}" + (f" (x{c})" if c > 1 else ""))
        print(f"    ({theirs_ph} target placeholder(s) account for some of these)")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("units", nargs="*")
    ap.add_argument("--all", action="store_true", help="check every built unit")
    ap.add_argument("--matched", action="store_true",
                    help="check only units at 100%% fuzzy — the ones where a wrong name is a "
                         "real defect rather than an unimplemented stub")
    ap.add_argument("-v", "--verbose", action="store_true", help="also list units that pass")
    args = ap.parse_args()

    if not shutil.which(OBJDUMP):
        sys.exit(f"{OBJDUMP} not found — install mingw-w64-binutils")

    all_units = json.loads((ROOT / "objdiff.json").read_text()).get("units", [])
    if args.matched:
        # An unimplemented stub trivially "references names the target does not" — the check
        # only carries meaning once a unit claims to reproduce the target.
        want = [u for u in all_units
                if u.get("base_path") and (ROOT / u["base_path"]).exists()
                and _fuzzy(u["name"]) >= 100.0]
        print(f"checking {len(want)} units at 100% fuzzy\n")
    elif args.all:
        want = [u for u in all_units
                if u.get("base_path") and (ROOT / u["base_path"]).exists()]
    else:
        names = set(args.units)
        want = [u for u in all_units if u["name"] in names]
        if not want:
            sys.exit("no units selected (use --all, or name units)")

    bad = [u["name"] for u in want if not check(u, args.verbose)]
    print(f"\nchecked {len(want)} units, {len(bad)} with relocation-name mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
