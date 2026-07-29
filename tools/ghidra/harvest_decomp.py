#!/usr/bin/env python3
"""Harvest Ghidra decompilations of ledger functions into a browsable on-disk corpus.

Writes one C file per function under analysis/cachebeta/decomp/<name>@<addr>.c, pulling from
the live `halo` pyghidra-mcp server (port 8031, see tools/ghidra/workspaces.json). Ported from
godzilla-decomp 2026-07-29 and re-parameterised for this target.

cachebeta.exe is stripped, so Ghidra names everything FUN_<addr>. As you identify functions and
record names in config/halo/functions.sqlite, this substitutes them back into the harvested C so
callees read with real names.

SEQUENTIAL by design: the single-JVM server wedges under concurrent decompile clients, so this
decompiles one function at a time.

NOTE ON SEEDING: the ledger is currently seeded per *translation unit* from config/config.json
(833 rows, addr=NULL) rather than per function, so this script has nothing to harvest until rows
with real addresses exist. Populate addresses first — e.g. from build/split/**.obj symbol tables
or from Ghidra's own function list — then run this.

Usage:
  python3 tools/ghidra/harvest_decomp.py                 # every named function
  python3 tools/ghidra/harvest_decomp.py --category ai
  python3 tools/ghidra/harvest_decomp.py --addr 0x47c060 # a single function
"""
import argparse, json, os, re, sqlite3, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLIENT = os.path.join(ROOT, "tools", "ghidra", "ghidra_client.py")
DB = os.path.join(ROOT, "config", "halo", "functions.sqlite")
OUTDIR = os.path.join(ROOT, "analysis", "cachebeta", "decomp")
PORT, BINARY = "8031", "/cachebeta.exe-d7dc40"


def decompile(addr):
    """Return (name, code) for the function at addr, or (None, None) on failure."""
    out = subprocess.run([sys.executable, CLIENT, PORT, "decompile", addr],
                         capture_output=True, text=True, timeout=90)
    try:
        obj = json.loads(out.stdout.strip())
    except Exception:
        return None, None
    code = (obj.get("code") or "").replace("\\n", "\n").replace("\\t", "\t")
    return obj.get("name"), code


def safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "fn")


def load_name_map(con):
    """addr-based FUN_ token -> applied name, for every named function in this workspace. pyghidra-mcp
    serves decompilations cached at analysis time, so renames don't appear in the C body; we
    substitute them back deterministically from the ledger so the corpus reads with real names."""
    m = {}
    for addr, name in con.execute(
            "SELECT addr,name FROM functions WHERE workspace='halo'"
            " AND name IS NOT NULL AND addr IS NOT NULL"):
        try:
            m["FUN_%08x" % int(addr, 16)] = name
        except ValueError:
            pass
    return m


def substitute_names(code, name_map):
    def repl(mo):
        return name_map.get("FUN_" + mo.group(0)[4:].lower(), mo.group(0))
    return re.sub(r"FUN_[0-9a-fA-F]{8}", repl, code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="only this ledger category")
    ap.add_argument("--addr", help="only this address (hex)")
    ap.add_argument("--overwrite", action="store_true", help="re-decompile even if the .c exists")
    a = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    con = sqlite3.connect(DB)
    q = "SELECT addr,name,category,status,match_pct,notes FROM functions WHERE workspace='halo'"
    params = []
    if a.addr:
        q += " AND addr=?"; params.append(a.addr)
    elif a.category:
        q += " AND category=?"; params.append(a.category)
    else:
        q += " AND addr IS NOT NULL"     # TU-seeded rows have no address yet
    rows = con.execute(q + " ORDER BY category,addr", params).fetchall()
    name_map = load_name_map(con)
    con.close()

    ok = skip = fail = 0
    for addr, name, cat, status, pct, notes in rows:
        path = os.path.join(OUTDIR, f"{safe(name)}@{addr}.c")
        if os.path.exists(path) and not a.overwrite:
            skip += 1; continue
        gname, code = decompile(addr)
        if not code:
            fail += 1; print(f"  FAIL {addr} {name}", file=sys.stderr); time.sleep(0.2); continue
        code = substitute_names(code, name_map)   # resolve FUN_<addr> callees to applied names
        header = (f"/* {name}  —  game@{addr}  [{cat}]  status={status}"
                  f"{f' match={pct}%' if pct else ''}\n"
                  f" * Harvested Ghidra decompilation (workspace halo, {BINARY}). Callees show\n"
                  f" * applied names where known. Ghidra label: {gname}.\n"
                  f"{(' * Note: ' + notes + chr(10)) if notes else ''}"
                  f" */\n\n")
        open(path, "w").write(header + code.strip() + "\n")
        ok += 1
        time.sleep(0.15)
    print(f"harvested {ok} decompilations to {os.path.relpath(OUTDIR, ROOT)} "
          f"({skip} already present, {fail} failed)")


if __name__ == "__main__":
    main()
