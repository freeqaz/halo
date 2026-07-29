-- config/godzilla/functions.sqlite schema
--
-- Lightweight gameplay-RE ledger for the Stern Godzilla `game` binary (and the shared
-- `spike-engine` reference binary). Tracks which stripped functions have been identified,
-- named, and objdiff-matched, plus supporting evidence (renames) and a string->xref index
-- used to jump from interesting strings to the functions that reference them.
--
-- This is intentionally separate from analysis/flows.sqlite (which is the generic
-- router-decomp-style surface/flow ledger, shared tooling) and cache.db (Ghidra
-- decompile/strings cache). functions.sqlite is Godzilla-specific naming/status tracking
-- for the objdiff match-build loop described in docs/plans/00-setup-plan.md.

CREATE TABLE IF NOT EXISTS functions (
  id         INTEGER PRIMARY KEY,
  addr       TEXT,               -- hex address in the target binary, e.g. "0x1a2b3c"
  name       TEXT,                -- current/assigned symbol name
  workspace  TEXT,                -- ghidra workspace this function lives in (godzilla, spike-engine, ...)
  category   TEXT,                -- e.g. node-bus, scoring, mode-sm, switch-handler, coil, audio, render, libc, unknown
  status     TEXT DEFAULT 'unknown',   -- unknown | identified | named | decompiled | match-building | matched | verified
  match_pct  REAL DEFAULT 0,      -- objdiff match percentage (0-100) for the reconstructed C candidate
  notes      TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_functions_addr     ON functions(addr);
CREATE INDEX IF NOT EXISTS idx_functions_status   ON functions(status);
CREATE INDEX IF NOT EXISTS idx_functions_category ON functions(category);

CREATE TABLE IF NOT EXISTS renames (
  addr     TEXT,   -- address of the function/symbol being renamed
  symbol   TEXT,   -- new symbol name applied
  evidence TEXT     -- why: string xref, call pattern, structural match, objdiff confirmation, etc.
);

CREATE INDEX IF NOT EXISTS idx_renames_addr ON renames(addr);

CREATE TABLE IF NOT EXISTS strings_index (
  addr    TEXT,   -- address of the string in the binary
  value   TEXT,   -- string contents
  xref_fn TEXT     -- address (or name once known) of the function referencing this string
);

CREATE INDEX IF NOT EXISTS idx_strings_index_addr    ON strings_index(addr);
CREATE INDEX IF NOT EXISTS idx_strings_index_xref_fn ON strings_index(xref_fn);
