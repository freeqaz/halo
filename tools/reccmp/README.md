# tools/reccmp — what reccmp is actually good for here

[reccmp](https://github.com/isledecomp/reccmp) is the matching-decomp toolchain from the
LEGO Island project. On paper it is the closest existing ecosystem to this repo's problem:
MSVC, x86, PE, matching a retail binary function by function. In practice **almost all of it
is inapplicable**, and the one part that is useful turned out to duplicate something csplit
already does.

The honest summary: reccmp bought us **one independent verification of csplit's PDB read**
and **a ledger population with translation-unit attribution**. It did not buy us any symbol,
type, or layout information the repo did not already have.

Installed as an optional dependency (`pyproject.toml`, extra `reccmp`). Run everything from
the repo root via `uv run`.

## Does `reccmp-cvdump` read PDB 2.0? Yes.

This was the thing worth testing. `cachebeta.pdb` is PDB 2.0 (`Microsoft C/C++ program
database 2.00`, CodeView `NB10`); `llvm-pdbutil` and `pdb-decompiler` both target 7.0 and
reject it outright. reccmp bundles Microsoft's own `cvdump.exe` 14.00.23611, which still
handles 2.0. It runs under wine, which this repo already needs for MSVC.

```sh
uv run reccmp-cvdump -p          ../halo-protos/ce_2002-01-14/cachebeta.pdb  # PUBLICS
uv run reccmp-cvdump -seccontrib ../halo-protos/ce_2002-01-14/cachebeta.pdb  # SECTION CONTRIB
uv run reccmp-cvdump -m          ../halo-protos/ce_2002-01-14/cachebeta.pdb  # MODULES
uv run reccmp-cvdump -s -g -l -t ../halo-protos/ce_2002-01-14/cachebeta.pdb  # the rest
```

All six streams parse, exit 0. Redirect stderr — under wine every run prints a page of
`libEGL warning` / `nodrv_CreateWindow` noise that has nothing to do with the PDB.

What is in them:

| Stream | Records | Useful for Halo's own code? |
|---|---:|---|
| PUBLICS | 19,092 | **Yes** — the only stream that covers Bungie code |
| SECTION CONTRIBUTIONS | 22,455 | **Yes** — address range → owning `.obj` |
| MODULES | 848 | **Yes** — 467 Bungie `.obj`, 380 XDK/CRT lib `.obj`, `* Linker *` |
| SYMBOLS | 2,761 `S_GPROC32`, 7,027 `S_BPREL32` | No — every one belongs to an XDK/CRT module |
| GLOBALS | 4,481 `S_UDT`, 400 `S_GDATA32` | No — same |
| LINES | — | No — `Mod::GetEnumLines failed` for all 467 Bungie modules |
| TYPES | 2,538 `LF_STRUCTURE`, 10,158 `LF_MEMBER` | No — see below |

The reason is in the `S_COMPILE2` record of every Bungie module:

```
** Module: "\halo\objects\halobetacache\cache_files.obj"
         Language: C
         Compiled without debugging info: yes          <-- this
         Frontend Version: Major = 13, Minor = 0, Build = 9254
```

For the 467 translation units this project is decompiling, the PDB is a **symbol table, not
a debug database**: names and address ranges, no types, no locals, no parameters, no line
numbers.

### Halo's own struct layout is not recoverable. Confirmed, not assumed.

cvdump finds 2,538 `LF_STRUCTURE` / `LF_CLASS` records with 1,370 distinct names. Every one
is XDK, CRT, D3D or WinSock. Filtering for Halo's `lower_snake_case` house style leaves 21
names, and all 21 are still library types (`sockaddr_in`, `lconv`, `tm`, `fd_set`,
`threadlocaleinfostruct`, `xbox_adpcmwaveformat_tag`, …). Zero hits for `cache_file`,
`bitmap_group`, `s_game_globals`, `scenario_*`, `*_datum`, `tag_*`.

This matches what Ghidra's `Msf200` reader concluded independently (see
`tools/ghidra/README.md`). Two different readers, same answer — the information is not in
the file. Use the CEA PDBs in `../halo-symbols/cea_2011-06-24_HCEX/` for layout.

Same story for vtables: 22 `??_7` symbols exist, all XDK C++ (`CDirectSoundBuffer`,
`CMcpxAPU`, `CXnNic`). Bungie's code is C and has none.

## `audit_csplit.py` — the one genuinely new capability

csplit is the only thing in this repo that reads `cachebeta.pdb`, and everything downstream
trusts its output (`config/symbols.json`, `config/contribs.json`, `config/splits.json`,
`config/config.json`). Nothing verified it. cvdump is an independent second reader, and it
is Microsoft's own, so agreement is strong evidence and disagreement is a csplit bug.

```sh
uv run python tools/reccmp/audit_csplit.py
uv run python tools/reccmp/audit_csplit.py --json analysis/reccmp_audit.json \
                                          --empty-units analysis/empty_units.txt
```

Exit code is 1 if any check disagrees, so it can gate CI. Current result — everything
agrees:

```
[1] symbols   cvdump  19048 addrs   csplit  23069 addrs
              PDB addresses csplit does not cover: 0
              renamed by the project: 1
              0x005c8bd0 PDB ['__alloca_probe'] -> repo ['__chkstk']
              provenance: 19092 from the PDB, 4011 project-recovered, 10 compiler labels
[2] contribs  cvdump  22455   csplit  22455
              row mismatches (addr/size/flags): 0
[3] modules   cvdump    848   csplit    833
              ambiguous Imod->module_index: 0
              object-name agreement: 757 ok, 0 mismatched
[4] empty     76 of 833 units have no section contribution
              -> 757 units actually carry code or data in cachebeta.exe
[5] progress  ledger reports 103/833 units matched = 12.36%
              but 73 of those 103 are empty units
              real figure: 30/757 = 3.96%
```

Four things fell out of writing this that are worth knowing:

**csplit's PDB extraction is exact.** All 22,455 contribution rows match cvdump on address,
size and characteristics — zero mismatches. Every PDB public address is covered. The 757
module-to-source-file assignments all agree. Whatever else csplit v0.0.2 gets wrong, it is
not misreading the PDB.

**`config/symbols.json` is a working database, not a PDB dump.** It has 23,112 names where
the PDB has 19,092, and `git log --follow config/symbols.json` shows 30 commits of
hand-editing ("misc ai\_debug work", "objects work"). So 4,011 of those names are the
*project's* recovered statics and jump tables, not ground truth — the PDB has no static
symbols for Bungie's modules at all. cvdump is what lets you tell the two apart, and that
provenance split is worth having in a matching decomp. Exactly one address disagrees on name:
`0x005c8bd0`, where the PDB says `__alloca_probe` and the repo says `__chkstk` — MSVC's two
names for the same stack probe.

**The 76 degenerate `build/split/` objects are explained.** They are exactly the 76 objdiff
units that no section contribution maps to — those PDB modules contributed *nothing* to
`cachebeta.exe`. csplit is faithfully emitting one object per module, and an object with no
content has no COFF symbol table, which is why objdiff-cli aborts on them and why
`../halo-report.sh` has to filter them.

The list is coherent: tag-definition tables (`*_definitions.c`), editor-only code
(`radiosity.c`, `bitmap_compress.c`, `sound_import.c`), and Win32 variants excluded on Xbox
(`dialogs.c`, `input_windows.c`, `shell_windows.c`, `transport_dns_winsock.c`).
`analysis/empty_units.txt` has all 76. Note the paths contain spaces
(`source/saved films/saved_films`), so split on lines, not whitespace.

**The TU-level progress figure is badly inflated, and the empty units are why.** An empty
source file trivially produces an empty object that trivially matches an empty target, so
every one of them reports as Matching. 73 of the 103 "matched" translation units are empty
units. The real figure is **30 of 757 = 3.96%**, not 103 of 833 = 12.36%.

That is a threefold overstatement, and 3.96% is consistent with the other numbers the
project reports (3.59% code match, 624/11,057 functions, 0.94% complete) in a way that
12.36% never was. `audit_csplit.py` check 5 recomputes this from the ledger on every run.

### Deliberately NOT acting on this yet

The obvious fix is to drop the 76 from `objdiff.json` or clear their `complete` flag. **Do not
do that yet.** "No section contribution" is evidence that a module contributed nothing to
`cachebeta.exe`, but it is not yet *proof*: the same observation is produced by a gap in our
own map. If our module→contribution mapping is incomplete — a module we mis-attributed, a
contribution we failed to parse, an object folded into another by the linker — a unit with real
code in the binary looks identical to a genuinely empty one from here.

The two readings are only distinguishable once we can account for the binary's code bytes
completely: every byte of `.text` attributed to some module, with no unclaimed regions. Until
then, dropping these units risks deleting 76 real translation units from the work list and
permanently hiding whatever is actually in them.

So the current position is: **report the honest number, keep the units.** `audit_csplit.py`
surfaces the discrepancy on every run; `../halo-report.sh` already filters them at scoring time
because objdiff-cli cannot parse them at all. Neither of those is destructive. Revisit dropping
them only after full `.text` coverage is established.

## `import_cvdump.py` — ledger population `workspace='cvdump'`

```sh
uv run python tools/reccmp/import_cvdump.py --dry-run
uv run python tools/reccmp/import_cvdump.py
uv run python tools/reccmp/import_cvdump.py --include-literals   # +9,868 anonymous pools
```

9,224 rows in `workspace='cvdump'`, distinct from `halo` / `pdb` / `units`. This is PDB
publics only — no project-recovered names, because mixing ground truth with inference in one
population defeats the point of having it. The 9,868 anonymous constant pools (`??_C@`
string literals, `__real@` float constants) are skipped by default.

**`category` is the owning source file**, spelled exactly as `name` on the `units` rows, so
the two populations join on plain equality. That join did not previously exist: the `units`
rows have `addr` NULL, so there was no way to ask which functions live in a given
translation unit.

```sh
sqlite3 config/halo/functions.sqlite "
  SELECT u.name, u.status, count(c.id) AS symbols
  FROM functions u LEFT JOIN functions c
    ON c.workspace = 'cvdump' AND c.category = u.name
  WHERE u.workspace = 'units'
  GROUP BY 1, 2 ORDER BY symbols DESC LIMIT 20"
```

1,659 of the 9,224 addresses are absent from `workspace='pdb'` (Ghidra's read of the same
file):

- **760 named `.data` globals** and 432 `.rdata` — `_game_engine_globals`,
  `_rasterizer_global_defaults`, `_global_water_density`, `_following_camera_zoom_levels`,
  `_collision_debug_ignore_object_index`. The ledger held **no** data symbols before this,
  and data match sits at 35.79%, so this is the population to work from.
- **254 `.text` symbols Ghidra's PDB applier dropped** — `_action_alert_begin`,
  `_real_random`, `_is_bored`, `_scripted_camera_next_camera_point`, `_editor_camera_get_speed`.
- The rest are XDK section symbols (`D3D`, `XPP`, `BINK`).

### How good is the attribution?

Spot-checked against the decomp's own source tree: of the code symbols cvdump attributes to
a `source/` unit whose `.c` exists, 614 are defined in exactly that file. 386 appear in some
other file too, but inspection shows those are *call sites* for functions nobody has written
yet (`__rasterizer_present` is called from `render.c`, will be defined in
`rasterizer_xbox.c`). No contradiction found. The remaining 3,710 are not in `source/` at
all yet — that is the 99% of the decomp still to do.

Two caveats:

- **345 symbols have no owning unit** (`category='unattributed'`). These sit outside every
  section contribution — import-library thunks from the modules csplit drops (`xbdm.dll`,
  `xboxkrnl.exe`, `OLDNAMES.lib`).
- **240 `.data` symbols land in `source/linker_common.c`.** That is the `* Linker *`
  pseudo-module, which the linker credits with its own generated data. `_debug_lights` and
  `_game_variant_global` really belong to a Bungie TU; the PDB does not say which.

## What is not worth wiring, and why

Every reccmp comparison tool takes the same four arguments:

```
--paths <original-binary> <recompiled-binary> <recompiled-pdb> <source-root>
```

**This repo has no linked output.** `build.ninja` has rules `cl`, `csplit`, `progress` and
`report` — and no link step at all. The build produces `.obj` files for objdiff and stops.
There is no recompiled binary and no recompiled PDB, so `reccmp-reccmp`, `reccmp-datacmp`,
`reccmp-stackcmp`, `reccmp-vtable`, `reccmp-roadmap`, `reccmp-verexp` and
`reccmp-ghidra-import` cannot run. Not "awkward" — structurally blocked. Producing one would
mean linking a 0.94%-complete decomp of 833 translation units.

They are also all driven by annotation comments in the source (`// FUNCTION:`, `// VTABLE:`,
`// GLOBAL:`). `grep -rlE '// (FUNCTION|STUB|GLOBAL|VTABLE|LIBRARY|STRING):' source/`
returns 0 files, and adding them is explicitly out of scope — this project is objdiff-based
and stays upstream-compatible with `punpckhdq/halo`.

Tool by tool:

- **`reccmp-vtable`** — irrelevant twice over. Needs `// VTABLE:` annotations, and Bungie's
  code is C with zero vtables. Fed the original PDB as if it were a recompiled one it
  reports `Vtables found: 0. 100% match.`
- **`reccmp-stackcmp`** — compares stack frame layout between original and recompiled
  functions. Needs the recompiled PDB. objdiff already shows register and stack-offset
  differences inline in the diff, which is the same information in the place you are already
  looking.
- **`reccmp-datacmp`** — compares data *values* between the two binaries, keyed on
  `// GLOBAL:` annotations. objdiff's data-section scoring covers this.
- **`reccmp-roadmap`** — orders modules by symbol count to suggest what to work on next. The
  ledger join above gives the same thing from data we already have, and respects unit status.
- **`reccmp-decomplint`** — lints annotation markers. Runs clean on `source/` because there
  are none.
- **`reccmp-aggregate`** — aggregates reccmp's own report JSON into SVG/HTML progress
  graphs. Wrong input format; `../halo-report.sh` already does this.
- **`reccmp-project`** — scaffolds `reccmp-project.yml` / `reccmp-build.yml`. Deliberately
  not run.

### reccmp as a library, though

Two pieces are annotation-free and worked first try. `cvdump_pdb.py` uses the first:

- **`reccmp.formats`** — clean PE/ELF/MachO readers. `detect_image(filepath=...)` gives
  sections with `virtual_address` (imagebase included) and `physical_range`, which is exactly
  the file-offset ↔ VA conversion csplit's JSON needs.
- **`reccmp.cvdump.demangler`** — pure-Python MSVC demangler, no wine. `demangle_vtable`,
  `get_vtordisp_name`, and `demangle_string_const`, which decodes `??_C@` names into
  `StringConstInfo(len=37, is_utf16=False)`. Not wired up: the 9,868 literal boundaries are
  derivable from consecutive addresses in `config/symbols.json` anyway. Worth remembering if
  `.rdata` layout matching ever gets fiddly.

## Files

| File | What |
|---|---|
| `cvdump_pdb.py` | shared PDB reader — runs `reccmp-cvdump`, parses PUBLICS / SECTION CONTRIBUTIONS / MODULES |
| `audit_csplit.py` | cross-checks `config/*.json` against cvdump; emits the empty-unit list; exit 1 on disagreement |
| `import_cvdump.py` | loads PDB publics into `workspace='cvdump'` with translation-unit attribution |
| `analysis/empty_units.txt` | the 76 units with no code or data in `cachebeta.exe` |

Nothing here writes to `source/`, `config/*.json`, `objdiff.json` or `build.ninja`. The only
mutation is `workspace='cvdump'` in `config/halo/functions.sqlite`, and re-running
`import_cvdump.py` replaces that population wholesale.
