#!/usr/bin/env python3
"""Cross-check csplit's PDB extraction against an independent cvdump read.

csplit is the only thing in this repo that reads cachebeta.pdb, and everything downstream
trusts what it writes into config/symbols.json, config/contribs.json, config/splits.json and
config/config.json. Nothing verified those files until now.

reccmp bundles Microsoft's own cvdump.exe, which is the only other tool available here that
can read PDB 2.0. That makes it a genuine second opinion: agreement is strong evidence the
extraction is right, and disagreement is a csplit bug worth reporting upstream.

    uv run python tools/reccmp/audit_csplit.py

Checks:

  1. Symbols     config/symbols.json vs cvdump PUBLICS, by address (see the note below on
                 why not by name).
  2. Contribs    config/contribs.json vs cvdump SECTION CONTRIBUTIONS, row by row
                 (address, size, characteristics).
  3. Modules     the module_index in contribs.json vs cvdump's Imod, then the resulting
                 module -> object-file name correspondence.
  4. Empty units the objdiff translation units that no section contribution maps to.
  5. Progress    TU completion recomputed with those empty units excluded.

Checks 4 and 5 are the reason this script exists, and they turned out to matter more than
the verification did. The empty units are why objdiff-cli aborts over build/split/ and why
../halo-report.sh has to filter them: csplit faithfully emits one object per PDB module, and
some PDB modules contributed nothing at all to cachebeta.exe, so the object it writes has no
symbol table for objdiff to read. Worse, an empty source file trivially "matches" an empty
target, so those units all report as Matching and inflate the progress figure threefold.

Exit code is 1 if any check disagrees, so this can gate CI.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path, PurePosixPath, PureWindowsPath

from cvdump_pdb import ANON_DATA, REPO, load_all

CONFIG = REPO / "config"

# cvdump module names that do not correspond to a real translation unit, so csplit is
# expected to name the object something else entirely.
LINKER_SYNTHETIC = {"* Linker *"}


def out_path(arg: str) -> Path:
    """Relative output paths are resolved against the repo root, not the cwd, so the
    script behaves the same however it is invoked."""
    p = Path(arg)
    return p if p.is_absolute() else REPO / p


def load_csplit() -> tuple[list[dict], list[dict], dict[int, tuple[str, str]], list[str]]:
    """csplit's four outputs. Symbols and contribs are keyed on *file offset*, not VA."""
    symbols = json.loads((CONFIG / "symbols.json").read_text())
    contribs = json.loads((CONFIG / "contribs.json").read_text())
    config = json.loads((CONFIG / "config.json").read_text())
    objects = {
        o["index"]: (p["name"], o["name"]) for p in config["projects"] for o in p["objects"]
    }
    units = [u["name"] for u in json.loads((REPO / "objdiff.json").read_text())["units"]]
    return symbols, contribs, objects, units


def unit_progress(empty_units: set[str]) -> tuple[int, int, int, int, int] | None:
    """Re-derive TU completion from the ledger with the empty units taken out.

    Returns (matched, total, matched_real, total_real, matched_that_are_empty), or None if
    the ledger has no workspace='units' population to read.
    """
    db = REPO / "config" / "halo" / "functions.sqlite"
    if not db.exists():
        return None
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT name, status FROM functions WHERE workspace = 'units'"
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    if not rows:
        return None
    matched = [n for n, s in rows if s in ("matched", "verified")]
    empty_matched = [
        n for n in matched if PurePosixPath(n).with_suffix("").as_posix() in empty_units
    ]
    return (
        len(matched),
        len(rows),
        len(matched) - len(empty_matched),
        len(rows) - len(empty_units),
        len(empty_matched),
    )


def file_offset_to_va(sections: list) -> callable:
    ranges = [(s.physical_range, s.virtual_address, s.name) for s in sections]

    def convert(offset: int) -> tuple[int | None, str | None]:
        for phys, va, name in ranges:
            if offset in phys:
                return va + (offset - phys.start), name
        return None, None

    return convert


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", metavar="FILE", help="write machine-readable findings here")
    ap.add_argument(
        "--empty-units",
        metavar="FILE",
        help="write the objdiff unit names with no section contribution, one per line "
        "(feed this to an objdiff/report exclusion list)",
    )
    args = ap.parse_args()

    publics, contribs, modules, sections = load_all()
    cs_symbols, cs_contribs, cs_objects, cs_units = load_csplit()
    to_va = file_offset_to_va(sections)
    failures = []

    # ---- 1. symbols ---------------------------------------------------------------
    # Compare by address, not by name. config/symbols.json is not a PDB dump — it is a
    # working database, seeded from the PDB and then hand-edited across 30 commits as
    # functions got identified (`git log --follow config/symbols.json`). So it holds names
    # the PDB never had, and it renames some that it did. Address coverage is the only
    # question cvdump can actually settle.
    # Several symbols can share one address (aliases, and MSVC's COMDAT folding), so keep
    # every name per address — otherwise a genuine alias looks like a rename.
    cs_by_addr: dict[int, set[str]] = {}
    for sym in cs_symbols:
        va, _ = to_va(sym["file_offset"])
        if va is not None:
            cs_by_addr.setdefault(va, set()).add(sym["name"])
    cv_by_addr: dict[int, set[str]] = {}
    for pub in publics:
        cv_by_addr.setdefault(pub.addr, set()).add(pub.name)

    uncovered = sorted(set(cv_by_addr) - set(cs_by_addr))
    renamed = sorted(
        (a, sorted(cv_by_addr[a] - cs_by_addr[a]), sorted(cs_by_addr[a]))
        for a in set(cv_by_addr) & set(cs_by_addr)
        if cv_by_addr[a] - cs_by_addr[a]
    )
    print(f"[1] symbols   cvdump {len(cv_by_addr):>6} addrs   csplit {len(cs_by_addr):>6} addrs")
    print(f"              PDB addresses csplit does not cover: {len(uncovered)}")
    for addr in uncovered[:10]:
        print(f"              UNCOVERED {addr:#010x} {sorted(cv_by_addr[addr])}")
    if uncovered:
        failures.append(f"{len(uncovered)} PDB public addresses absent from config/symbols.json")
    print(f"              renamed by the project: {len(renamed)}")
    for addr, cv, cs in renamed[:5]:
        print(f"              {addr:#010x} PDB {cv} -> repo {cs}")

    # Provenance split. Names not in the PDB are the project's own work (statics, jump
    # tables, split-out data blobs); knowing which is which tells you what to trust.
    cv_names = {p.name for p in publics}
    project_names = {s["name"] for s in cs_symbols} - cv_names
    labels = {n for n in project_names if n.startswith(("$L", "$T", "$SG", "$M"))}
    unexpected = project_names - labels
    print(f"              provenance: {len(cv_names)} from the PDB, "
          f"{len(unexpected)} project-recovered, {len(labels)} compiler labels")
    if unexpected:
        print(f"              project-recovered sample: {sorted(unexpected)[:6]}")

    # ---- 2. contributions ---------------------------------------------------------
    print(f"[2] contribs  cvdump {len(contribs):>6}   csplit {len(cs_contribs):>6}")
    if len(contribs) != len(cs_contribs):
        failures.append("contribution row count differs")
    row_mismatch = 0
    for cv, cs in zip(contribs, cs_contribs):
        cs_va, _ = to_va(cs["file_offset"])
        if cs_va != cv.addr or cs["size"] != cv.size or cs["flags"] != cv.flags:
            row_mismatch += 1
    print(f"              row mismatches (addr/size/flags): {row_mismatch}")
    if row_mismatch:
        failures.append(f"{row_mismatch} contribution rows disagree")

    # ---- 3. module -> object correspondence ---------------------------------------
    # Both tools emit contributions in the same order, so zipping them recovers the
    # cvdump-Imod <-> csplit-module_index mapping without having to guess an offset
    # (csplit renumbers: it drops import-library and OLDNAMES modules).
    imod_to_index: dict[int, set[int]] = {}
    for cv, cs in zip(contribs, cs_contribs):
        imod_to_index.setdefault(cv.module, set()).add(cs["module_index"])
    ambiguous = {k: v for k, v in imod_to_index.items() if len(v) != 1}
    mapping = {k: next(iter(v)) for k, v in imod_to_index.items() if len(v) == 1}
    stem_ok = stem_bad = 0
    bad_stems = []
    for imod, index in sorted(mapping.items()):
        obj = cs_objects.get(index)
        if obj is None:
            # csplit dropped this module (import libs, OLDNAMES.lib thunks, "* Linker *").
            continue
        cv_stem = PureWindowsPath(modules[imod].obj).stem.lower()
        cs_stem = PurePosixPath(obj[1]).stem.lower()
        if cv_stem == cs_stem or modules[imod].obj in LINKER_SYNTHETIC:
            # "* Linker *" is the module the linker attributes its own generated data to
            # (thunks, the CRT init tables). csplit gives it a real filename so the decomp
            # has somewhere to put that code; the names deliberately differ.
            stem_ok += 1
        else:
            stem_bad += 1
            bad_stems.append((imod, modules[imod].obj, index, obj[1]))
    print(f"[3] modules   cvdump {len(modules):>6}   csplit {len(cs_objects):>6}")
    print(f"              ambiguous Imod->module_index: {len(ambiguous)}")
    print(f"              object-name agreement: {stem_ok} ok, {stem_bad} mismatched")
    for row in bad_stems[:10]:
        print(f"              MISMATCH {row}")
    if ambiguous or stem_bad:
        failures.append("module correspondence is not 1:1")

    # ---- 4. empty units -----------------------------------------------------------
    contributing = {c["module_index"] for c in cs_contribs}
    empty = sorted(set(cs_objects) - contributing)
    empty_units = [PurePosixPath(cs_objects[i][1]).with_suffix("").as_posix() for i in empty]
    print(f"[4] empty     {len(empty_units)} of {len(cs_objects)} units have no section "
          f"contribution")
    print(f"              -> {len(cs_objects) - len(empty_units)} units actually carry code "
          f"or data in cachebeta.exe")
    stray = set(empty_units) - set(cs_units)
    if stray:
        failures.append(f"{len(stray)} empty objects are not objdiff units")
    for name in empty_units[:8]:
        print(f"              {name}")
    if len(empty_units) > 8:
        print(f"              ... and {len(empty_units) - 8} more")

    # ---- 5. what the empty units do to the progress figures ------------------------
    # An empty source file trivially produces an empty object that trivially matches an
    # empty target, so every empty unit reports as Matching. That inflates the TU-level
    # completion number badly, and it is worth saying out loud.
    progress = unit_progress(set(empty_units))
    if progress:
        done, total, done_real, total_real, empty_done = progress
        print(f"[5] progress  ledger reports {done}/{total} units matched "
              f"= {done / total * 100:.2f}%")
        print(f"              but {empty_done} of those {done} are empty units")
        print(f"              real figure: {done_real}/{total_real} "
              f"= {done_real / total_real * 100:.2f}%")

    if args.empty_units:
        dest = out_path(args.empty_units)
        # Paths contain spaces (source/saved films/...), so consumers must split on lines.
        dest.write_text("\n".join(empty_units) + "\n")
        print(f"\nwrote {len(empty_units)} unit names to {dest}")

    if args.json:
        payload = {
            "symbols": {
                "cvdump_addrs": len(cv_by_addr),
                "csplit_addrs": len(cs_by_addr),
                "uncovered": [[f"{a:#010x}", sorted(cv_by_addr[a])] for a in uncovered],
                "renamed": [[f"{a:#010x}", cv, cs] for a, cv, cs in renamed],
                "from_pdb": len(cv_names),
                "project_recovered": sorted(unexpected),
                "compiler_labels": len(labels),
            },
            "contribs": {
                "cvdump": len(contribs),
                "csplit": len(cs_contribs),
                "row_mismatches": row_mismatch,
            },
            "modules": {
                "cvdump": len(modules),
                "csplit": len(cs_objects),
                "stem_agree": stem_ok,
                "stem_mismatch": bad_stems,
                "imod_to_module_index": {str(k): v for k, v in sorted(mapping.items())},
            },
            "empty_units": empty_units,
            "progress": (
                {
                    "matched_reported": progress[0],
                    "units_reported": progress[1],
                    "matched_real": progress[2],
                    "units_real": progress[3],
                    "matched_that_are_empty": progress[4],
                }
                if progress
                else None
            ),
            "failures": failures,
        }
        dest = out_path(args.json)
        dest.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote findings to {dest}")

    # Not part of the pass/fail checks, just a reminder of what the PDB cannot give us.
    anon = sum(1 for p in publics if ANON_DATA.match(p.name))
    print(f"\nnote: {anon} of {len(publics)} publics are anonymous constant pools "
          f"(string/float literals)")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nall checks agree: csplit's PDB extraction matches cvdump")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
