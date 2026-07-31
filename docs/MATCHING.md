# Matching techniques for MSVC 13.00.9254 (Xbox XDK, Aug 2001)

Everything here was learned by matching real units in this repo and **verified by byte-identical
output**, usually by trying the opposite and watching the score drop. This compiler ships only in
the Xbox XDK — no retail Visual C++ reproduces its codegen — so its habits are worth writing down.

## The loop

```sh
python3 tools/show_target.py <unit>                             # READ THE TARGET FIRST
flock /tmp/claude/halo-build.lock ninja build/base/<unit>.obj   # build one object
python3 tools/score_unit.py <unit> --functions                  # score it
```

### Start from the target object, not a decompiler

`build/split/**/*.obj` was carved out of `cachebeta.exe` by csplit **using the original PDB**, so
each object carries real symbol names and COFF relocations. `objdump -d -r` therefore resolves
every call target to its actual name:

```
  19:  e8 00 00 00 00    call   1e <_font_get_character_by_ascii_code+0x1e>
            1a: DISP32   _tag_block_get_element_with_size
```

That is the code you are trying to reproduce, exactly, with callee names already resolved. A
decompiler is a *reconstruction* of it and can add control-flow and type noise of its own. Four
units were matched to 100% in one session working purely from `objdump` output plus CEA field
names, without opening Ghidra at all.

**This is not an argument against the Ghidra workbench** — it holds 7,840 PDB-applied names and
27,309 types, and is the right tool for breadth: finding callers, understanding what a callback is
for, naming things across the whole image. But for the per-unit matching loop it is not the
starting point. `tools/show_target.py` wraps the objdump invocations (`--symbols`, `--data`,
`--headers`, `--base` to dump our own object for comparison).

`flock` matters only when several people or agents build at once; concurrent `ninja` in one build
directory can corrupt `.ninja_log`. `score_unit.py` never mutates `objdiff.json`, so it is always
safe to run in parallel.

**Read the two metrics correctly.** `matched_code_percent` is *exact* — a function contributes
zero unless it is byte-identical. `fuzzy_match_percent` is graded. A unit at 99.97% fuzzy can
report 79% exact, and that is correct, not a tooling bug. For data-only units look at the
per-section fuzzy number; the unit-level `matched_data` stays at 0 until bytes match exactly.

## Codegen levers, in rough order of usefulness

### 1. Name CSE-able values as explicit temporaries, computed once up front

The highest-value technique found so far. For x87 code, computing a value once into a named local
and referring to it repeatedly reproduces MSVC's FPU-stack duplication-and-reuse pattern
(`fld %st(1)`, `fmul %st(3),%st`); calling the same function inline at each use site emits reloads
or repeated calls instead.

```c
/* matches: one fcos/fsin pair, reused off the x87 stack */
real cos_angle1 = cosine(angle1), sin_angle1 = sine(angle1);
forward->i = cos_angle1 * cos_phi;
forward->j = cos_angle1 * sin_phi;

/* does NOT match: reloads angle1 and re-calls cosine at each use */
forward->i = cosine(angle1) * cos_phi;
forward->j = cosine(angle1) * sin_phi;
```

This took `seed_random_orientation` from 78.59% to 99.88% in one edit. Try it *first* on anything
trigonometric or with repeated derived values — it is cheap and has an outsized payoff. Reaching
for statement reordering before this is usually wasted effort.

### 2. Declaration position and block scope are load-bearing

Where a local is declared changes when its initialiser is loaded, and block scope changes register
allocation across the whole function. This is not cosmetic.

Verified destructively: hoisting `table_size` above an assignment in
`seed_random_vector_in_cone3d` and folding away a nested block dropped the unit from 100% to
78.91% exact / 98.76% fuzzy. A nested block that looks like clutter may be the only thing
producing the right allocation — **comment such blocks so nobody tidies them away.**

### 3. Register calling convention tells you `static` vs `extern`

MSVC 13 applies a custom register convention (arguments in e.g. `%si`/`%ebx`, no prologue) only to
**internal-linkage** functions whose address is never taken. So a target function receiving
arguments in registers with no stack prologue is `static`. This is a reliable oracle, and it also
tells you the function's position: keep it where the addresses put it in the original source order
rather than moving it under a `/* ---------- private code */` banner.

### 4. Argument push order is *not* compiler freedom

cdecl pushes strictly right-to-left, so push order **is** source argument order. If the target
pushes `eax` then `ecx` and you push `ecx` then `eax`, and the loads feeding them are otherwise
identical, you have the arguments the wrong way round in your source — not an evaluation-order
artifact.

This cost a whole function once: a 2-byte diff in `seed_random_orientation` was written off as
unreachable-from-C when it was really `yaw_vectors(forward, up, …)` where the original had
`yaw_vectors(up, forward, …)`. The swapped version was also semantically wrong. **Before
concluding "no source-level lever", check whether the bytes are telling you the code is incorrect.**

### 4a. Ternary into a pointer, then one unconditional dereference

When the disassembly shows a conditional pointer computation whose branches **converge on a single
dereference site**, write it as a ternary feeding one deref — not an if/else with the dereference
duplicated in both arms:

```c
/* matches: one computation site, one deref */
struct font_character *c = (index != NONE) ? &table[index] : NULL;
return c->foo;
```

Two separate dereferences, one per branch, generate visibly different code. This is the
value-selection analogue of the guard-shape rule (#6), which covers early exits.

### 4b. The result-variable idiom

When a register is zeroed early, reused across every exit path, and moved to `eax` at a single
tail (`mov eax, ebx` at the end), the original used one result variable and one `return` — not
multiple returns:

```c
struct font_character *result = NULL;
...
return result;
```

Combine with #2: **where** you declare that variable matters. In `font_group` the target zeroed
`result` *after* the first call, and moving the declaration one line down was the entire
difference between 96% and 100%.

### 4c. `const` decides `.data` vs `.rdata`

If a global lands in the wrong section, the usual cause is a missing `const`. A non-`const`
definition goes to `.data`; the target may put it in `.rdata`. Adding `const` to **both** the
`extern` declaration in the header and the definition in the `.c` moves it and can take a unit
straight from 0% to an exact match — this was the whole of
`source/sound/sound_environment_definitions`.

Check which section the target symbol lives in first (`tools/show_target.py <unit> --symbols`);
it tells you what qualifier the original had.

### 4d. Boolean parameters are normalised, and `MIN`/`MAX` are macros

Two idioms that look like free choices in C but are not:

- `test` / `setne` in the target means the source normalised a boolean explicitly —
  `(flag != FALSE)` rather than a plain assignment, which emits a direct `movzx`.
- A **default value computed first, then conditionally overwritten** is the register shape of the
  repo's `MIN`/`MAX` macros in `cseries.h` (`((a)>(b)?(b):(a))`), *not* an `if`-statement
  reassignment. Reach for the macro.

Both came out of `source/units/unit_definitions`, each costing a build/score cycle to discover.
Read the disassembly for these shapes *before* writing "obviously equivalent" C.

### 5. Float constants fold across inlined call boundaries

If an inlinable function's body ends in `* literalA` and the call site immediately multiplies by
`literalB`, MSVC folds them into a single constant. If the target keeps them separate, split the
expression across two statements to prevent the fold.

### 6. Guard shape controls FP comparison codegen

For float-compare-guarded early exits, MSVC here favours a *positive guard wrapping the main body
with a single trailing return* over the more natural early-return idiom. The two produce different
flag-mask/jump-mnemonic pairs and place the exit block differently. If an early return is close but
not matching, try inverting it.

## Types: use evidence, never invent padding

Halo's own struct layouts are **not** in `cachebeta.pdb` — all 467 Bungie modules were compiled
without debug info, so only XDK/CRT/XNet types survive. Layout evidence comes from:

1. **`../halo-symbols/cea_2011-06-24_HCEX/`** — the CEA PDB extraction, 10,146 files whose
   `projects/code/hcex/sources/` tree mirrors all 38 of this repo's source directories. The repo's
   convention is to take **CEA field names verbatim** (compare `source/units/biped_definitions.h`
   against CEA's `_biped_definition` — identical down to `turning_unused[4]`). Caveat: CEA is Halo
   *PC*-derived with Saber modifications, so it is strong evidence, not ground truth.

   **Read `projects/code/hcex/sources/<dir>/<unit>.c` before `exported.h`.** The flattened
   `exported.h` confirms raw field lists but loses context — it drops `tag_block` element-type
   comments and real parameter names. The `.c` files carry real global declarations, real function
   signatures with real parameter names, and sometimes the actual type name where a guess would be
   wrong (`sound_environment` has no `_definition` suffix, for instance).
2. **The repo itself.** Check for an existing incomplete type before naming a new struct — a
   header elsewhere may already reference it. `struct projectile_material_response_definition` was
   already declared in `source/objects/damage.h` while a new header defined it under a different
   name, so the definition never completed the type its own repo was waiting on.
3. **The disassembly**, for offsets and access widths.

`unused0` / `unused8` placeholder fields invented to reach a size are a maintenance hazard and
usually mean the real definition was one grep away. If you cannot find evidence, say so explicitly
rather than inventing a plausible-looking field.

## House style

- Include order: `cseries.h` and the unit's own header, blank line, then everything else. Put
  `math/real_math.h` before `tag_files/tag_groups.h`.
- Keep the `/* ---------- headers */`, `/* ---------- constants */`, … banner sequence.
- `match_assert` / `match_vassert` / `match_malloc` carry literal `c:\halo\SOURCE\...` paths and
  line numbers — that is deliberate, not a leak.
- Completed units end `void` functions with an explicit `return;`.
- Enum families get a trailing `NUMBER_OF_…` terminator.

## ninja does not track header dependencies

Editing a `.h` will **not** rebuild the `.c` files that include it — `ninja` reports "no work to
do" and you get a stale object. After any header change, delete the affected objects by hand:

```sh
rm -f build/base/source/interface/terminal.obj
flock /tmp/claude/halo-build.lock ninja build/base/source/interface/terminal.obj
```

For a header included widely, `rm -rf build/base && ninja all_source` is the only safe check. This
matters most when verifying you have *not* regressed other units: a clean "no work to do" is
meaningless here.

## Scoring ceilings are real, but prove them

Some units cannot reach 100% for reasons outside the source. `source/items/projectile_definitions`
tops out at 93.02326% because three `dir32` relocations to a folded empty-string COMDAT were
attributed by csplit to `source/ai/action_obey.obj` and left undefined here.

That was proven, not asserted, by scoring **the target object against a byte-identical copy of
itself** — it also reports 93.02326%. Do that before accepting any "unfixable" claim; it is a few
minutes of work and the alternative is abandoning a fixable unit.
