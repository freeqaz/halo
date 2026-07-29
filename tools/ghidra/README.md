# tools/ghidra — RE workbench

Ported from `~/code/godzilla-decomp/tools/ghidra` on 2026-07-29 and re-parameterised for this
target. `ghidractl` itself is vendor-agnostic and was copied unmodified — all target layout
lives in `workspaces.json`.

## Quick start

```sh
./tools/ghidra/ghidractl ls          # registry + up/down state
./tools/ghidra/ghidractl up halo     # launch the workspace (first run: import + analyse)
./tools/ghidra/ghidractl status      # readiness
./tools/ghidra/ghidractl attach halo # register in .mcp.json
./tools/ghidra/ghidractl down halo
```

First build of the `halo` workspace took ~76 s (import + full analysis of a 6.5 MB PE).
Reopening an analysed project is fast. Servers launch with `--wait-for-analysis`, so
"port is listening" means ready.

## Workspaces

| Name | Port | Binary | State |
|---|---:|---|---|
| `halo` | 8031 | `cachebeta.exe` — i386 PE, the match target | ✅ working, 8,954 functions |
| `cea` | 8032 | `HCEX.xex` / `HCEX_Release.xex` — Xbox 360 PPC reference | not yet built |

Ports 8021–8023 belong to `godzilla-decomp`; this repo uses 8031+.

**The `halo` workspace should be rebuilt with the PDB applied** — see "PDB names" below. It
was built without, so it has 291 real names where it could have 7,840.

### Known gaps

Both former blockers are resolved, but **only in the fork install**, not in `/opt/ghidra`:

```
/home/free/code/milohax/ghidra/build/ghidra-dist/ghidra_12.2_DEV/Ghidra/Extensions/
    ghidra-xbe/      (name=XboxExecutableLoader, version=12.2)
    XEXLoaderWV/     (version=12.2)
```

- **`cachebeta.xbe` now imports** — `ghidra-xbe` was built from source against the 12.2 fork.
  Base `0x10000`, entry `0x1d59d8`, 25 memory blocks, 8,951 functions, 647 named. See
  `../../docs/DECOMPILERS.md` for the full numbers and the exec-bit bug that had been silently
  suppressing 356 of those names.
- **`cea` (the XEXs) is unblocked** — `XEXLoaderWV` is present at 12.2 in the same install. The
  12.0.1 ZIP under `~/.config/ghidra/` is no longer needed.

**Consequence for `workspaces.json`: `ghidra_install_dir` still points at `/opt/ghidra` (12.1.2),
which has neither extension.** Repoint it at the fork's `build/ghidra-dist/ghidra_12.2_DEV` to
use them, and rebuild the affected projects — extensions bind at JVM start, so already-running
servers are unaffected. Weigh this against the fact that all existing numbers in this README were
measured on 12.1.2.

## PDB names — the highest-leverage step

`../halo-protos/ce_2002-01-14/cachebeta.pdb` is **PDB 2.0** (`NB10`). pdb-decompiler can't
read it, which is why `../halo-symbols/README.md` originally called it stripped — but Ghidra
12.1.2 has an `Msf200` reader and gets **7,840 function names, 6,525 of them Bungie's own**
(`collision_test_line`, `bitmap_group_try_and_get_bitmap`, …), plus 27,309 types.

Ghidra will not find the PDB on its own: the embedded path is `c:\halo\objects\...` and the
file is outside the repo. `SetPdb.java` sets it explicitly and allows the untrusted path.

```sh
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
/opt/ghidra/support/analyzeHeadless <projdir> <projname> \
    -import cachebeta.exe \
    -scriptPath tools/ghidra \
    -preScript  SetPdb.java ../halo-protos/ce_2002-01-14/cachebeta.pdb \
    -postScript DumpFuncs.java          # writes /tmp/claude/pdbtest/names.txt

python3 tools/ghidra/import_pdb_names.py /tmp/claude/pdbtest/names.txt
```

Expect ~30 warnings of the form `PDB STRUCTURE reconstruction failed to align …` — those are
individual XDK aggregates, not a failure of the run. Watch for
`PDB Types and Main Symbols Processing Terminated Normally`.

Only Halo's **own struct layout** is truly absent: of 1,736 composites Ghidra builds, 1,675
have members but all are XDK/CRT/XNet (`D3DXCOLOR`, `CSocket`). Use the CEA PDBs in
`../halo-symbols/cea_2011-06-24_HCEX/` for layout.

## BinExport / BinDiff

`bindiff` is installed system-wide (`/usr/bin/bindiff`). Its Ghidra exporter was built for
`ghidra_12.1_DEV` and has been copied into `~/.config/ghidra/ghidra_12.1.2_DEV/Extensions/`,
along with `PatchDiffCorrelator`.

The `version=` in each `extension.properties` was re-stamped to `12.1.2` as hygiene, but note
that **Ghidra does not actually gate on this** — `validateExtensionVersion` is a private method
of `ghidra.framework.project.extensions.ExtensionInstaller`, reachable only from the GUI
*Install Extensions* dialog, and it offers an "Install Anyway" override rather than refusing.
Headless module discovery, and any extension unzipped into `Ghidra/Extensions` by hand, never
look at the version at all. So a version mismatch is not the reason an extension fails to load
— look for a real `ClassNotFoundException`/`NoSuchMethodError` in the log instead.

Cross-*build* diffing (`cachebeta.exe` vs another i386 Halo build) is the useful case.
Diffing against the CEA XEXs is i386-vs-PowerPC and BinDiff's structural correlators degrade
badly across architectures — prefer Ghidra's Version Tracking there.
- **Ghidra assigns hash-suffixed binary names** (`/cachebeta.exe-d7dc40`). Use the exact name
  from `list_project_binaries`; the bare path is rejected.
- `code_indexed` and `strings_indexed` are false, so semantic `search_code` is unavailable.
  Use `search_symbols_by_name` and `decompile_function`.

## Driving it

`ghidra_client.py` talks MCP-over-HTTP directly, so agents can use it without a session
restart:

```sh
python3 tools/ghidra/ghidra_client.py 8031 tools
python3 tools/ghidra/ghidra_client.py 8031 decompile 0x0047c060
python3 tools/ghidra/ghidra_client.py 8031 call search_symbols_by_name \
    '{"binary_name":"/cachebeta.exe-d7dc40","query":"^FUN_","functions_only":true,"limit":10}'
```

`.mcp.json` also registers `ghidra-halo` as a session MCP server (gitignored — it is
machine-local and rewritten by `ghidractl mcp`).

## `harvest_decomp.py`

Decompiles ledger functions into `analysis/cachebeta/decomp/<name>@<addr>.c`, substituting
applied names from the ledger so callees read properly. Sequential by design — the single-JVM
server wedges under concurrent decompile clients.

```sh
python3 tools/ghidra/harvest_decomp.py                  # every named function
python3 tools/ghidra/harvest_decomp.py --category ai
python3 tools/ghidra/harvest_decomp.py --addr 0x0047c060
```

## The ledger — `config/halo/functions.sqlite`

Schema from godzilla (`config/halo/schema.sql`), unmodified. **Tracked in git** — naming work
is shared; only the Ghidra projects and caches are ignored.

Two populations, separated by `workspace`:

Three populations, separated by `workspace`:

| `workspace` | Rows | Meaning |
|---|---:|---|
| `halo` | 8,954 | Ghidra functions in `cachebeta.exe`, `addr` set. 291 already have real names; the rest are `FUN_*`. Built **without** the PDB — rebuild. |
| `pdb` | 7,840 | Names recovered from `cachebeta.pdb`, `addr` set, `status='named'`. 6,525 are non-`library`. Ground truth for identity, says nothing about match state. |
| `units` | 833 | objdiff translation units from `config/config.json`, `addr` NULL. `category` = source subdirectory; status seeded from the decomp's own Matching/NonMatching/MISSING (103 / 363 / 367). |

The split matters: `harvest_decomp.py` and the naming tools query `workspace='halo'`, while
per-TU match tracking lives in `units` and lines up with what `../halo-report.sh` reports.
`pdb` is a reference population — join it on `addr` to name anything in `halo`.

```sh
sqlite3 config/halo/functions.sqlite "
  SELECT h.addr, p.name FROM functions h JOIN functions p ON h.addr = p.addr
  WHERE h.workspace='halo' AND p.workspace='pdb' AND h.name LIKE 'FUN_%' LIMIT 10"
```

```sh
sqlite3 config/halo/functions.sqlite \
  "SELECT category, count(*) FROM functions WHERE workspace='units' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
```

## Not yet ported

`apply_names.py`, `sync_from_ledger.py`, `export_ghidra_annotations.py`,
`build_naming_context.py`, `context_to_corpus.py` and the `wf_*.js` workflow scripts remain in
godzilla-decomp. They are lightly parameterised (target names are constants at the top) and can
be ported the same way when needed.
