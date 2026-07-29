#!/usr/bin/env python3
"""Read cachebeta.pdb with reccmp's cvdump wrapper and normalise the result.

cachebeta.pdb is PDB 2.0 (MSF "program database 2.00", CodeView NB10). llvm-pdbutil and
pdb-decompiler both target PDB 7.0 and reject it. reccmp ships Microsoft's own
cvdump.exe (14.00.23611), which still handles 2.0 — it runs under wine here, which is
already a dependency of this repo's MSVC toolchain, so nothing new is required.

This module is the shared PDB reader for the other scripts in this directory. It does not
touch the repo; `audit_csplit.py` and `import_symbols.py` are the entry points.

Streams and what is actually in them for THIS binary:

    PUBLICS (-p)      19,092 S_PUB32 records. The only stream that covers Halo's own code.
    SECTION CONTRIB   22,455 rows mapping <section:offset,size> to a module (.obj) index.
    MODULES (-m)      848 modules: 467 Bungie .obj, 380 XDK/CRT lib .obj, "* Linker *".
    SYMBOLS (-s)      Per-module symbols, but Bungie's 467 modules all report
                      "Compiled without debugging info: yes" — every S_GPROC32 (2,761),
                      S_BPREL32 (7,027) and S_UDT (30,724) belongs to an XDK/CRT module.
    LINES (-l)        "Mod::GetEnumLines failed" for all 467 Bungie modules.
    TYPES (-t)        2,538 LF_STRUCTURE, none of them Halo's. See README.md.

So for the code this project is decompiling, the PDB is a *symbol* table, not a debug
database: names and address ranges, no types, no locals, no line numbers.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "cachebeta.exe"
# Outside the repo on purpose: the PDB is 5.4 MB of someone else's build output and lives
# with the rest of the proto haul.
PDB = REPO.parent / "halo-protos" / "ce_2002-01-14" / "cachebeta.pdb"

# cvdump prints "[ssss:oooooooo]" where ssss is a 1-based PE section index.
_PUBLIC = re.compile(r"^S_PUB32: \[([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})\], Flags: \w{8}, (.+)$")
_CONTRIB = re.compile(
    r"^\s+([0-9A-Fa-f]{4})\s+([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})\s+"
    r"([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s*$"
)
# Either `IIII "lib" "obj"` (from a library) or `IIII "obj"` (linked directly).
_MODULE = re.compile(r'^([0-9A-Fa-f]{4}) "([^"]*)"(?: "([^"]*)")?')

# Compiler-generated constant pools. Real names, but they identify anonymous data, so the
# function ledger has no use for them and they would triple its row count.
ANON_DATA = re.compile(r"^(\?\?_C@|__real@|__xmm@)")


@dataclass(frozen=True)
class Public:
    addr: int  # virtual address, imagebase included
    section: str  # PE section name, e.g. ".text"
    name: str


@dataclass(frozen=True)
class Contrib:
    module: int  # 1-based cvdump module index ("Imod")
    addr: int
    size: int
    flags: int


@dataclass(frozen=True)
class Module:
    index: int
    obj: str  # e.g. "\\halo\\objects\\halobetacache\\cache_files.obj"
    lib: str | None  # e.g. "...\\Xbox\\Lib\\dsound.lib", or None if linked directly


def run_cvdump(flag: str, pdb: Path = PDB) -> str:
    """Invoke reccmp-cvdump and return stdout.

    stderr is swallowed: under wine every run emits a page of `libEGL warning` and
    `nodrv_CreateWindow` noise that has nothing to do with the PDB.
    """
    if not pdb.exists():
        sys.exit(f"PDB not found: {pdb}")
    proc = subprocess.run(
        ["uv", "run", "reccmp-cvdump", flag, str(pdb)],
        cwd=REPO,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if proc.returncode != 0 or "Debugging Information Dumper" not in proc.stdout:
        sys.exit(
            f"reccmp-cvdump {flag} failed (rc={proc.returncode}).\n"
            f"stderr tail:\n{proc.stderr[-2000:]}"
        )
    return proc.stdout


def pe_sections() -> list:
    """PE section table via reccmp's own reader. `virtual_address` already includes the
    imagebase, and `physical_range` is the file-offset range csplit's JSON is keyed on."""
    from reccmp.formats.detect import detect_image

    return list(detect_image(filepath=TARGET).sections)


def _va(sections: list, index: int, offset: int) -> tuple[int, str] | None:
    if not 1 <= index <= len(sections):
        return None
    sec = sections[index - 1]
    return sec.virtual_address + offset, sec.name


def parse_publics(text: str, sections: list) -> list[Public]:
    out = []
    for line in text.splitlines():
        m = _PUBLIC.match(line.strip())
        if not m:
            continue
        va = _va(sections, int(m[1], 16), int(m[2], 16))
        if va:
            out.append(Public(va[0], va[1], m[3]))
    return out


def parse_contribs(text: str, sections: list) -> list[Contrib]:
    out = []
    for line in text.splitlines():
        m = _CONTRIB.match(line)
        if not m:
            continue
        va = _va(sections, int(m[2], 16), int(m[3], 16))
        if va:
            out.append(Contrib(int(m[1], 16), va[0], int(m[4], 16), int(m[5], 16)))
    return out


def parse_modules(text: str) -> dict[int, Module]:
    out = {}
    for line in text.splitlines():
        m = _MODULE.match(line)
        if not m:
            continue
        # Two-string form is `"lib" "obj"`; one-string form is the obj itself.
        obj, lib = (m[3], m[2]) if m[3] else (m[2], None)
        out[int(m[1], 16)] = Module(int(m[1], 16), obj, lib)
    return out


def load_all(pdb: Path = PDB) -> tuple[list[Public], list[Contrib], dict[int, Module], list]:
    """Three cvdump invocations, ~12 s total under wine."""
    sections = pe_sections()
    publics = parse_publics(run_cvdump("-p", pdb), sections)
    contribs = parse_contribs(run_cvdump("-seccontrib", pdb), sections)
    modules = parse_modules(run_cvdump("-m", pdb))
    return publics, contribs, modules, sections


def main() -> int:
    publics, contribs, modules, sections = load_all()
    print(f"{len(publics)} publics, {len(contribs)} contributions, {len(modules)} modules")
    bungie = sum(1 for m in modules.values() if "halobetacache" in m.obj)
    print(f"  {bungie} Bungie modules, {len(modules) - bungie} library/linker modules")
    for sec in sections[:1] + [s for s in sections if s.name in (".rdata", ".data")]:
        n = sum(1 for p in publics if p.section == sec.name)
        print(f"  {sec.name:<10} {n:>6} publics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
