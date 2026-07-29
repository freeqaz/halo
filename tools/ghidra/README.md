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

### Known gaps

- **`cachebeta.xbe` does not import.** Ghidra 12.1.2 has no XBE loader. Only `cachebeta.exe`
  is in the project — verified, not assumed. It stays in `workspaces.json` as documentation of
  intent; loading it needs an XBE loader extension or a manual raw import.
- **The `cea` workspace needs XEXLoaderWV.** The server logs
  `install_plugin failed with zip: [Errno 21] Is a directory:
  /home/free/code/milohax/XEXLoaderWV/XEXLoaderWV` — the checkout is there but pyghidra-mcp
  wants a built `.zip` extension. Build it before `ghidractl up cea`.
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

| `workspace` | Rows | Meaning |
|---|---:|---|
| `halo` | 8,954 | Ghidra functions in `cachebeta.exe`, `addr` set. 291 already have real names; the rest are `FUN_*`. |
| `units` | 833 | objdiff translation units from `config/config.json`, `addr` NULL. `category` = source subdirectory; status seeded from the decomp's own Matching/NonMatching/MISSING (103 / 363 / 367). |

The split matters: `harvest_decomp.py` and the naming tools query `workspace='halo'`, while
per-TU match tracking lives in `units` and lines up with what `../halo-report.sh` reports.

```sh
sqlite3 config/halo/functions.sqlite \
  "SELECT category, count(*) FROM functions WHERE workspace='units' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
```

## Not yet ported

`apply_names.py`, `sync_from_ledger.py`, `export_ghidra_annotations.py`,
`build_naming_context.py`, `context_to_corpus.py` and the `wf_*.js` workflow scripts remain in
godzilla-decomp. They are lightly parameterised (target names are constants at the top) and can
be ported the same way when needed.
