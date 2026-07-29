#!/usr/bin/env python3
"""Import cachebeta.pdb public symbols into the ledger, attributed to their objdiff unit.

The ledger already knows PDB *names* (workspace='pdb', 7,840 rows from Ghidra's Msf200
reader) and objdiff *units* (workspace='units', 833 rows) — but the two cannot be joined,
because the unit rows have addr NULL. So there is no way to ask the obvious question:
"which functions live in source/cache/cache_files.c, and how many of them are named?"

This fills that in. cvdump's SECTION CONTRIBUTIONS stream maps every address range in
cachebeta.exe to the .obj that produced it, and csplit's config/config.json maps those
module indices to source paths, which are exactly objdiff's unit names. Joining the two
gives every PDB symbol an owning translation unit.

    uv run python tools/reccmp/import_cvdump.py

Rows land in workspace='cvdump', distinct from 'halo' (live Ghidra state), 'pdb' (Ghidra's
read of the same PDB) and 'units' (objdiff TUs).

Two things this population has that workspace='pdb' does not:

  * ~1,200 named data globals (_game_engine_globals, _rasterizer_global_defaults,
    _global_water_density, ...). The ledger held no data symbols at all, and data match
    sits at 35.79%, so these are the ones to work from.
  * ~470 code symbols Ghidra's PDB applier dropped (_action_alert_begin, _real_random,
    _is_bored, ...).

`category` is the owning source file, spelled exactly as `name` on the workspace='units'
rows, so the two join on plain equality:

    -- how many PDB symbols does each unit own, and what state is the unit in?
    SELECT u.name, u.status, count(c.id) AS symbols
    FROM functions u LEFT JOIN functions c
      ON c.workspace = 'cvdump' AND c.category = u.name
    WHERE u.workspace = 'units'
    GROUP BY 1, 2 ORDER BY symbols DESC;

    -- the biggest units nobody has started
    SELECT u.name, count(c.id) AS symbols FROM functions u
    JOIN functions c ON c.workspace = 'cvdump' AND c.category = u.name
    WHERE u.workspace = 'units' AND u.status NOT IN ('matched', 'verified')
    GROUP BY 1 ORDER BY symbols DESC LIMIT 20;

Note this is PDB *publics* only, so statics are absent — the PDB has no static symbols for
Bungie's 467 modules (they were compiled without debugging info). config/symbols.json holds
another ~4,000 names the project recovered by hand; those are not imported here, because
mixing ground truth with inference in one population defeats the point of having it.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import PurePosixPath

from cvdump_pdb import ANON_DATA, REPO, load_all

DB = REPO / "config" / "halo" / "functions.sqlite"
WORKSPACE = "cvdump"


def unit_for_module(repo_config: dict) -> dict[int, str]:
    """csplit module_index -> source path, e.g. "source/cache/cache_files.c".

    Keeping the extension makes this identical to `name` on the ledger's workspace='units'
    rows, so the two populations join on plain equality. objdiff's own unit name is the
    same string without the extension.
    """
    return {
        o["index"]: PurePosixPath(o["name"]).as_posix()
        for p in repo_config["projects"]
        for o in p["objects"]
    }


def module_index_map(cv_contribs: list, cs_contribs: list[dict]) -> dict[int, int]:
    """cvdump Imod -> csplit module_index.

    Both tools walk the PDB's contribution table in order, so zipping recovers the mapping
    without guessing an offset. csplit renumbers because it drops the import-library and
    OLDNAMES.lib modules. audit_csplit.py verifies this is 1:1.
    """
    seen: dict[int, int] = {}
    for cv, cs in zip(cv_contribs, cs_contribs):
        seen.setdefault(cv.module, cs["module_index"])
    return seen


def attribute(publics: list, contribs: list, imod_to_unit: dict[int, str]) -> list[tuple]:
    """Assign each public symbol the unit of the contribution containing its address.

    Contributions do not overlap, so a sorted-start binary search is enough. Symbols land
    outside every contribution only in the import-library modules csplit drops.
    """
    ranges = sorted((c.addr, c.addr + c.size, c.module) for c in contribs)
    starts = [r[0] for r in ranges]
    out = []
    for pub in publics:
        i = bisect.bisect_right(starts, pub.addr) - 1
        unit = None
        if i >= 0 and pub.addr < ranges[i][1]:
            unit = imod_to_unit.get(ranges[i][2])
        out.append((pub.addr, pub.name, unit, pub.section))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--include-literals",
        action="store_true",
        help="also import the ~9,900 anonymous constant pools (??_C@ string literals, "
        "__real@ float constants). Off by default: they are addresses of unnamed data and "
        "would more than double the row count.",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only, do not write")
    args = ap.parse_args()

    publics, contribs, _modules, _sections = load_all()
    cs_contribs = json.loads((REPO / "config" / "contribs.json").read_text())
    repo_config = json.loads((REPO / "config" / "config.json").read_text())

    index_to_unit = unit_for_module(repo_config)
    imod_to_unit = {
        imod: index_to_unit[idx]
        for imod, idx in module_index_map(contribs, cs_contribs).items()
        if idx in index_to_unit
    }

    kept = publics if args.include_literals else [p for p in publics if not ANON_DATA.match(p.name)]
    rows = attribute(kept, contribs, imod_to_unit)
    skipped = len(publics) - len(kept)
    orphan = sum(1 for r in rows if r[2] is None)

    print(f"{len(publics)} publics; {skipped} anonymous constant pools skipped")
    print(f"{len(rows)} to import, {orphan} with no owning unit (import-library thunks)")

    if args.dry_run:
        for addr, name, unit, section in rows[:15]:
            print(f"  {addr:#010x} {section:<8} {unit or '-':<40} {name}")
        return 0

    now = datetime.now(UTC).isoformat(timespec="seconds")
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM functions WHERE workspace = ?", (WORKSPACE,))
    con.executemany(
        "INSERT INTO functions (addr, name, workspace, category, status, notes, updated_at) "
        "VALUES (?, ?, ?, ?, 'named', ?, ?)",
        [
            (f"0x{addr:08x}", name, WORKSPACE, unit or "unattributed",
             f"cvdump PUBLICS; section={section}", now)
            for addr, name, unit, section in rows
        ],
    )
    con.commit()

    total = con.execute(
        "SELECT count(*) FROM functions WHERE workspace = ?", (WORKSPACE,)
    ).fetchone()[0]
    print(f"\nimported {total} rows into workspace='{WORKSPACE}'")

    # What this adds over the Ghidra-sourced population.
    new_addrs = con.execute(
        "SELECT count(*) FROM functions c WHERE c.workspace = ? AND NOT EXISTS "
        "(SELECT 1 FROM functions p WHERE p.workspace = 'pdb' AND p.addr = c.addr)",
        (WORKSPACE,),
    ).fetchone()[0]
    print(f"{new_addrs} addresses not present in workspace='pdb'")

    print("\nunits with the most PDB symbols:")
    for unit, n in con.execute(
        "SELECT category, count(*) FROM functions WHERE workspace = ? "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
        (WORKSPACE,),
    ):
        print(f"  {n:>5}  {unit}")

    print("\nlargest units not yet matched, by PDB symbol count:")
    for unit, n in con.execute(
        "SELECT u.name, count(c.id) FROM functions u JOIN functions c "
        "  ON c.workspace = ? AND c.category = u.name "
        "WHERE u.workspace = 'units' AND u.status NOT IN ('matched', 'verified') "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
        (WORKSPACE,),
    ):
        print(f"  {n:>5}  {unit}")

    silent = con.execute(
        "SELECT count(*) FROM functions u WHERE u.workspace = 'units' AND NOT EXISTS "
        "(SELECT 1 FROM functions c WHERE c.workspace = ? AND c.category = u.name)",
        (WORKSPACE,),
    ).fetchone()[0]
    print(f"\n{silent} units own no PDB public symbol at all — 76 of those are the empty "
          f"units (see audit_csplit.py), the rest hold only statics and constants")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
