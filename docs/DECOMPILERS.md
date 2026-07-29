# Decompilers and RE tooling for this target

The target is an **i386 PE built by pre-release MSVC 13.00.9254** (`cachebeta.exe`). That
combination — x86, MSVC, and a *matching* decomp rather than a readable one — narrows what is
worth installing considerably.

## `cachebeta.exe` is an Xbox PE, not a Win32 one

Worth stating up front, because it is easy to get wrong (this file was described as "the Win32
build" in earlier notes here). The PE optional header reports **subsystem 14 =
`IMAGE_SUBSYSTEM_XBOX`**, and the section table is Xbox-specific — 26 sections:

```
.text D3D D3DX DSOUND XNET BINK BINK32 BINK32A BINK16 BINK4444 BINK5551 BINK16MX
BINK16X2 BINK16M BINK32MX BINK32X2 BINK32M XPP .rdata .data DOLBY BINKDATA INIT
.tls .XBLD .reloc
```

`D3D`/`DSOUND`/`XNET`/`XPP`/`DOLBY`/`.XBLD` are XDK static libraries given their own sections.
So this is the **Xbox executable in PE form** — the input the XDK's `imagebld` converts into an
XBE — not a desktop Windows build that happens to share the architecture. Which is why
`cachebeta.xbe` ships beside it in the same package. Ordinary i386 tooling still applies
(it is a valid PE at ImageBase 0x00400000), but do not expect Win32 assumptions to hold.

The load-bearing point: in a matching decomp the decompiler is not the bottleneck. Correctness
is decided by `objdiff` scoring our compiled object against the split target object, not by how
pleasant any tool's C output reads. Decompiler prose is an input to writing the candidate, and
Ghidra's is already the best free x86 decompiler. **Symbols, types, and cross-build diffing move
the needle far more than a second decompiler does.**

## Python environment

`uv`, from `pyproject.toml` at the repo root:

```sh
uv sync --extra build --extra reccmp --extra mcp
uv run reccmp-cvdump --help
```

Upstream's build path (`configure.py`, `tools/download_tool.py`, `tools/vsgen/*`) is
**deliberately stdlib-only plus `certifi`**, so `python3 configure.py && ninja` works with no
virtualenv at all. Keep it that way — it matters for sending PRs back to `punpckhdq/halo`. All
our additions live in optional-dependency groups. `uv.lock` is tracked; `.venv/` is not.

## Ranked by actual value

### 1. `cachebeta.pdb` applied in Ghidra — worth doing, but not a discovery

Applying the PDB inside Ghidra names 7,840 functions (6,525 of them Bungie's own) and builds
27,309 types, up from 291 names. That is worth doing — it makes decompiled output readable and
callees self-describing — but it is **not new information**.

**The repo already ships a superset.** `config/symbols.json` is tracked and contains **23,112**
symbols (name + `file_offset` + flags), and `config/contribs.json` has 22,455 section
contributions. csplit reads this PDB correctly and completely; a second independent reader found
exactly one name csplit lacks (`__alloca_probe`, which csplit calls `__chkstk` — same address,
MSVC alias). So the value here is *getting the names into Ghidra*, not obtaining them.

The format trap is still real and still worth knowing: the file is **PDB 2.0** (`NB10`), not
PDB 7.0 (`RSDS`). `pdb-decompiler` and `llvm-pdbutil` produce almost nothing from it; Ghidra's
`Msf200` reader and reccmp's `cvdump` both handle it. `../halo-symbols/README.md` recorded this
PDB as stripped for exactly that reason and has been corrected.

**Halo's own struct layout is genuinely absent**, now confirmed by two independent readers. The
reason is in every Bungie module's `S_COMPILE2` record: `Compiled without debugging info: yes`,
for all 467 of them. No types, no locals, no parameters, no line numbers for Halo's own code —
only the XDK/CRT/D3D/WinSock types that came in via linked libraries. Use the CEA PDBs in
`../halo-symbols/cea_2011-06-24_HCEX/` for layout; there is nothing more to extract here.

### 2. reccmp — the closest thing to an ecosystem for this problem

`pip`-installable, already in the `reccmp` extra. From the LEGO Island decomp, so it is built
for MSVC x86 matching decomps specifically. Ships `reccmp-cvdump` (a PDB reader that covers the
2.0 format), plus `vtable`, `stackcmp`, `datacmp`, `roadmap`, `verexp`, `decomplint` and a
Ghidra importer.

**Evaluated: a poor fit. Keep one script from it.** Full detail in `tools/reccmp/README.md`.

`reccmp-cvdump` does read this PDB 2.0 file (under wine), and all six streams parse. But it finds
*fewer* symbols than `config/symbols.json` already has, and every one of its comparison tools —
`reccmp`, `datacmp`, `stackcmp`, `vtable`, `roadmap`, `verexp`, `ghidra-import` — requires
`--paths <original> <recompiled-binary> <recompiled-pdb> <source-root>`. **This repo has no link
step**: `build.ninja` has rules `download_tool`, `cl`, `csplit`, `progress`, `report`, `configure`
and zero link edges. There is no recompiled binary or PDB to compare against, so those tools are
structurally blocked rather than merely awkward. They are also annotation-driven, and `source/`
has no `// FUNCTION:`/`// VTABLE:` markers. `reccmp-vtable` is irrelevant twice over — Bungie's
code is C, and all 22 `??_7` symbols in the PDB are XDK C++.

What survives:

- **`tools/reccmp/audit_csplit.py`** — a second independent reader cross-checking csplit's output.
  Worth having in CI, and it is what surfaced the progress-inflation bug below.
- **`reccmp.formats`** as a library — a clean PE reader giving `virtual_address`/`physical_range`,
  i.e. the file-offset↔VA conversion this project needs constantly.
- **`reccmp.cvdump.demangler`** — a pure-Python MSVC demangler, no wine required.

We did **not** restructure the repo to reccmp's project layout or annotate `source/`; upstream
compatibility matters for sending PRs back to `punpckhdq/halo`.

### 3. BinExport + BinDiff — cross-build function matching

`bindiff` was already installed system-wide (`/usr/bin/bindiff`). Its Ghidra exporter had been
built for `ghidra_12.1_DEV` while `/opt/ghidra` is 12.1.2, so it was copied into
`~/.config/ghidra/ghidra_12.1.2_DEV/Extensions/` with `version=` re-stamped, as was
`PatchDiffCorrelator`. The re-stamp is hygiene only — contrary to what an earlier revision of
this file claimed, Ghidra does **not** gate on extension version outside the GUI installer
dialog (see `tools/ghidra/README.md`).

Use it for i386-vs-i386 across Halo builds. Against the CEA XEXs it is x86-vs-PowerPC, where
BinDiff's structural correlators degrade badly; use Ghidra's Version Tracking for that axis.

### 4. RetDec — evaluated and rejected

Built cleanly at `~/code/milohax/retdec` (`8be53bbd`), so this is a measured verdict, not a
guess. **Do not wire `retdec-decompiler` into any workflow.**

It builds in ~2m40s with zero source patches, but needs two things:

- **CMake ≤ 3.31.** The vendored LLVM 8 fork declares `cmake_minimum_required(VERSION 3.4.3)`
  and CMake 4 hard-errors on it; `-DCMAKE_POLICY_VERSION_MINIMUM` does not help because
  `deps/llvm/CMakeLists.txt` hardcodes its own `CMAKE_ARGS`. Arch's CMake cannot build upstream
  RetDec. A portable 3.31.6 under `/tmp/claude/tools/` sidesteps it.
- **`-DCMAKE_CXX_FLAGS="-include cstdint"`** for RetDec's *own* sources — `borland_ast_parser.h`
  uses `enum Status : uint8_t` without including `<cstdint>`, which libstdc++ 16 no longer
  provides transitively. LLVM 8 itself compiles clean under GCC 16.

Whole-binary decompilation of the 6.5 MB PE *is* feasible — 500 s, **17.9 GiB peak RSS**,
750k lines — so the usual "too big for RetDec" worry does not apply. The problem is the output.

**It silently deletes stores and call arguments.** On a codebase this dense with `printf`-style
assert/error logging, that is fatal: **423 of 437** calls in the whole-binary output supply fewer
arguments than their format string's `%` specifiers. RetDec infers a too-short prototype for a
variadic logger and then dead-code-eliminates everything feeding the discarded arguments. It also
fails to model a 3-float stack vector as aliasing, deleting two of three `fstp` stores, and its
x87/`float80_t` handling is specifically bad for a 2002 MSVC x86 game. Ghidra gets all of these
right.

A second opinion is only worth having if its disagreements are informative. RetDec's are mostly
its own bugs, and they produce plausible, compilable C that is missing behaviour — the worst
failure mode for matching work.

**Keep `retdec-fileinfo` though.** It is independent of the decompiler and genuinely useful: it
identifies the linker and dumps the Rich header, giving a free TU count and toolchain provenance
(706 C + 81 C++ objects at cl build 9254, linker 9290, plus 11/12/35 objects from builds
7291/8444/8803 — the prebuilt Bink/D3D/XNET static libs).

### 5. dewolf — readability, not a second analysis

`fkie-cad/dewolf`. Ghidra-backed, but emits genuinely idiomatic C (real loops and conditionals
instead of `goto` webs). **Not on PyPI** — it is a Ghidra plugin plus a Python frontend,
installed from source and pinned to a Ghidra version, which is why it is not a `pyproject.toml`
extra. Same underlying analysis as Ghidra, so it improves how the input reads without finding
anything new.

### 6. angr — for indirect branches, not for its C output

Cloned at `~/code/milohax/angr-decompiler` but `angr` is not importable (no environment). An
`angr` extra exists in `pyproject.toml`. Its value here is **symbolic execution** to recover
jump tables and computed constants that Ghidra leaves as unresolved indirect branches — not its
decompiler.

## Deliberately skipped

| Tool | Why not |
|---|---|
| Snowman | Unmaintained since ~2017, strictly worse than Ghidra. |
| reko | Competent, but its x86 output is not better and integration is real work. |
| rev.ng | Primarily a research platform; heavy for what it returns here. |
| Binary Ninja | Costs money, and does not clearly beat Ghidra on x86. |
| **IDA 9 + Hex-Rays** | The one paid tool that *would* change things — materially better x86 decompiler and a deeper diffing ecosystem. Worth revisiting if a licence becomes available. |
| `m2c` | MIPS and PowerPC only. Recorded in `decomp-synth.json` as unavailable for this target. |

## Xbox-side tooling

`cachebeta.exe` is the Win32 build and the actual match target, but the same package ships
`cachebeta.xbe`, `cachebeta_CG.xbe` and `cachebeta_instrumented.xbe` — the Xbox executables.
Ghidra has no XBE loader in the box, so these do not import (verified, see
`tools/ghidra/README.md`).

**Both are now built and working** — clone at `~/code/milohax/ghidra-xbe`, built from source
against the 12.2 fork and installed into `~/code/milohax/ghidra/build/ghidra-dist/ghidra_12.2_DEV`
(which already carried `XEXLoaderWV` at 12.2). Zero 12.0.3→12.2 API breakage; all 8 Java sources
compiled unmodified. Four local fixes were needed — see that repo's README.

The one that matters: Ghidra's `buildExtension.gradle` zips every entry mode `0644`, so the
bundled `XbSymbolDatabaseCLI` native binaries ship **non-executable**. The analyzer then fails in
`ProcessBuilder.start()`, catches `Throwable`, and returns — **analysis reports success while
recovering zero library symbols.** Fixed with a `filesMatching { permissions { unix(0755) } }`
block. Impact on `cachebeta.xbe`:

| | before fix | after |
|---|---:|---:|
| Named (non-`FUN_*`) functions | 291 | **647** |
| Library-namespace functions | 16 | **384** |

All 536 symbols `XbSymbolDatabaseCLI` emits for that file now land (D3D8 152, DSOUND 156,
XAPILIB 52, XNET 8, plus 16 `xboxkrnl.exe` thunks). This implies the **upstream prebuilt release
ZIPs are broken on Linux/macOS** for the same reason.

`cachebeta.xbe` loads at base `0x10000`, entry `0x1d59d8`, 25 memory blocks, 8,951 functions.
`cachebeta_instrumented.xbe` is essentially identical; `cachebeta_CG.xbe` has 28 blocks and
10,786 functions but XbSymbolDatabase only matches 94 symbols in it. The XTLID analyzer no-ops on
all three — it wants a `.XTLID` section and these have `$$XTIMAGE`/`$$XSIMAGE`. Not a bug.

- **`mborgerson/xbox-includes`** supplies `xbox.h` — note it is *not* under the `XboxDev` org
  (that URL 404s), and `xbox.h` is **not checked in**: `make` generates it via `gcc -E -P`
  (157 KB, 6,969 lines). Cloned to `~/code/milohax/xbox-includes`.
- **The GUI is not required.** `ghidra-xbe/ghidra_scripts/ApplyXboxHeaders.java` does it headlessly
  via `CParserUtils.parseHeaderFiles` + `ApplyFunctionDataTypesCmd`, wrapped in explicit
  transactions (headless post-scripts run *outside* any transaction). Result: **+2,073 data types**,
  851 `FunctionDefinition`s, and **283 functions given real prototypes**. Order matters —
  `ApplyFunctionDataTypesCmd` matches by symbol name, so the XbSymbolDatabase analyzer must run
  first; on a program without those names it applies zero signatures.
- `ghidra-xbe` has an open feature request for external `.pdb`/`.map` loading, so XBE symbols need
  aligning by hand. Less painful than it sounds: `cachebeta.pdb` describes the PE form of the same
  build, which we already have fully named.
- **`emoose/idaxex`** (IDA 9) passes CodeView info to IDA, prompts for matching PDBs, and applies
  XbSymbolDatabase/XTLID names — the cleaner route for PDB-bearing Xbox builds, but requires IDA.
- **`sp00nznet/xboxrecomp`** does static recompilation to native Windows executables, with an
  optional Ghidra naming pass. Out of scope for a matching decomp; relevant if the goal ever
  shifts to a runnable port.
