#!/usr/bin/env python3
"""Import cachebeta.pdb function names into the ledger.

cachebeta.pdb is PDB 2.0 (MSF "program database 2.00", CodeView NB10). pdb-decompiler
cannot read its type stream, which is why ../../../halo-symbols/ records it as "stripped" —
but Ghidra 12.1.2 has an Msf200 reader and recovers 7,840 function names, ~6,500 of them
Bungie's own (collision_test_line, bitmap_group_try_and_get_bitmap, ...).

Produce the input with the DumpFuncs.java script under a Ghidra project that has the PDB
applied (see README.md, "PDB names"):

    analyzeHeadless <proj> <name> -process cachebeta.exe -noanalysis -readOnly \
        -scriptPath tools/ghidra -postScript DumpFuncs.java

then:

    python3 tools/ghidra/import_pdb_names.py names.txt

Rows land in workspace='pdb' so they never collide with workspace='halo' (live Ghidra
state) or workspace='units' (objdiff TUs). status='named', because a PDB name is ground
truth for identity but says nothing about whether we have matching C for it yet.
"""

import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "config" / "halo" / "functions.sqlite"
WORKSPACE = "pdb"

# Names that came from the XDK, the CRT or the import thunks rather than Halo itself.
# Kept in the ledger (they still identify real code) but categorised separately so
# `category != 'library'` gives you the Bungie surface.
LIBRARY_RE = re.compile(r"^(_|\?|@|thunk_|Ordinal_|FID_|j_|D3D|Direct|IDirect|X[A-Z][a-z])")


def categorise(name: str) -> str:
    """Bucket a symbol by its leading identifier, which in Halo's C tracks the
    source subdirectory closely enough to be useful (bitmap_* -> bitmaps, ...)."""
    if LIBRARY_RE.match(name):
        return "library"
    head = re.match(r"^([a-z][a-z0-9]*)", name)
    return head.group(1) if head else "unknown"


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} <names.txt from DumpFuncs.java>")
    src = Path(sys.argv[1])
    now = datetime.now(UTC).isoformat(timespec="seconds")

    rows = []
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        addr, _, name = line.partition("\t")
        if not name:
            continue
        rows.append(("0x" + addr.lower().lstrip("0").rjust(8, "0"), name, categorise(name)))

    con = sqlite3.connect(DB)
    con.execute("DELETE FROM functions WHERE workspace = ?", (WORKSPACE,))
    con.executemany(
        "INSERT INTO functions (addr, name, workspace, category, status, notes, updated_at) "
        "VALUES (?, ?, ?, ?, 'named', 'from cachebeta.pdb via Ghidra Msf200 reader', ?)",
        [(a, n, WORKSPACE, c, now) for a, n, c in rows],
    )
    con.commit()

    total = con.execute(
        "SELECT count(*) FROM functions WHERE workspace = ?", (WORKSPACE,)
    ).fetchone()[0]
    game = con.execute(
        "SELECT count(*) FROM functions WHERE workspace = ? AND category != 'library'",
        (WORKSPACE,),
    ).fetchone()[0]
    print(f"imported {total} names into workspace='{WORKSPACE}' ({game} non-library)")

    print("\ntop categories:")
    for cat, n in con.execute(
        "SELECT category, count(*) FROM functions WHERE workspace = ? AND category != 'library' "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 12",
        (WORKSPACE,),
    ):
        print(f"  {cat:<14} {n}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
