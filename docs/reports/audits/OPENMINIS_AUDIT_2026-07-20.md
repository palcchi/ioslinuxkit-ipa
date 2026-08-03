# OpenMinis `ish-arm64` audit — 2026-07-20

> **Dated report:** This audit applies to `rcarmo/ios-linuxkit` commit `35dac743` and OpenMinis refs observed on 20 July 2026. Later commits require a new comparison.

## Scope

Compared `rcarmo/ios-linuxkit` `origin/master` (`312f1093`) with every live ref in
`OpenMinis/ish-arm64` on 2026-07-20:

- 10 branches
- tag `v2.0.0`
- all 21 pull requests, including closed/unmerged PRs
- OpenMinis `master` through `89269e6f` (merged PR #21)

The repositories diverged at `5d0af765`, so patches were reviewed semantically
against the newer rcarmo tree rather than merged wholesale.

## Imported

The audit imported 31 isolated correctness commits, resolving them against the
newer ARM64/JIT, terminal and rootfs work already on rcarmo `origin/master`.
They cover:

- fakefs SQLite init failures and transient-lock retries
- exec/exit `mm` lifetime, deferred cleanup and teardown race guards
- Darwin host-stat failure handling and Mach host-port reference caching
- `/proc/<pid>/fd` exit races, NULL-fd handling and lock inversion
- stale ARM64 poke state, TLB generations and self-modifying-code invalidation
- ORR/EOR-to-SP correctness and CASP/STXP pair width/alignment/atomicity
- `MADV_FREE`/`MADV_DONTNEED` semantics and mapped-range validation
- epoll regular-file semantics, fd-key identity and `EPOLLONESHOT` lifetime
- `timer_create(NULL)` and `pidfd_open`/pidfd polling
- realtime signal queueing, `SA_ONSTACK` and guarded `SA_RESTART`
- non-blocking writer acquisition needed to avoid Darwin JIT/GC deadlock
- allocate-and-swap `mm` ordering across `exec`

## Already present under rcarmo commits

OpenMinis changes for `clone3`, `membarrier`, `preadv2`/`pwritev2`, ARM64 vector
`REV16`, pair load/store support, reservation-aware high mmap selection and
several atomic decoder fixes were already present in the rcarmo tree in a
newer/different form. They were not duplicated.

## Deliberately omitted

- native/prebuilt gadget offload framework: large experimental feature, not an
  isolated correctness fix
- benchmark reports, generated test payloads and diagnostic-only tracing
- app marketing/version/TestFlight assets
- rejected PR #4 signpost instrumentation
- closed PR #5 as a standalone change; its useful SQLite tuning is already
  included as best-effort setup in the fakefs resilience import
- redundant branch tips and superseded intermediate fixes (blocking lock
  fallback, per-page file `pread`, diagnostic-only revisions)

## Validation

Host: Orange Pi 6 Plus, CIX P1, Debian Trixie, AArch64.

- `CC=clang make build-arm64-linux-all`: PASS (release and debug)
- release runtime coverage: 82/83 twice; all 47 C/ARM64 checks passed,
  including precise faults, fusion paths, signals, barriers and SMC
  invalidation
- transient Go failure passed immediately on focused retry
- remaining release-suite Clojure failure is rootfs packaging: the configured
  `/usr/share/clojure/clojure.jar` does not contain `clojure.main`; the full
  tools jar is a separate package artifact and is too slow for the suite limit
- debug runtime coverage: all 47 C/ARM64 checks and Go/Bun/Node/Python/Lua
  checks passed; the heavier Java/Rust failures are debug-JIT timeout/artifact
  effects rather than focused correctness failures
- focused atomics: CAS128, CLREX/STXR, LDXP/STLXP (32/64), LDXR widths: PASS
- focused regression program: `timer_create(NULL)`, epoll regular-file `EPERM`,
  `EPOLLONESHOT` disable/rearm, file-private `MADV_DONTNEED`, `SA_ONSTACK`,
  realtime signal queueing, `pidfd_open` + poll: PASS
- `git diff --check origin/master..HEAD`: PASS
- `git fsck --full`: PASS (only expected dangling objects from audit rebases)

GNU `as` rejects the tree's existing named-register `.req` syntax; this was
reproduced on untouched `origin/master`. Clang's integrated assembler is the
project's configured/default ARM64 toolchain and builds cleanly.

## Follow-up — OpenMinis issue #22

Reviewed issue #22 on 21–27 July 2026. Its `FCVTL`/`FCVTL2` request was already
implemented, and the reported `0x2e617800` opcode is `FCVTL`, not `FCVTXN`.
The missing instructions were:

- `FCVTN`/`FCVTN2`, single-to-half and double-to-single
- `FCVTXN`/`FCVTXN2`, double-to-single round-to-odd

The follow-up adds exact decoders and native gadgets, tightens the existing
`FCVTL` mask so reserved or other size encodings are not claimed, and runs
these conversions with guest `FPCR`/`FPSR` while restoring host thread state.

`make test-arm64-fcvt-vector` builds one static fixture and runs it first on the
AArch64 host as the architectural oracle, then under iSH. It covers both vector
halves, destination/source aliasing, lower-half zeroing, upper-half
preservation, guest rounding mode, cumulative `FPSR.IXC`, widening, and decoder
mask collisions. Clean Clang release and debug builds and the focused gate pass
on the Orange Pi 6 Plus.

## Follow-up — upstream iSH `/proc/<pid>/mem` seek crash

Reviewed `ish-app/ish` commit `297832fad03e318bcc10b9525da208902d5e9da7`
(PR #2646) on 3 August 2026. It prevents a NULL callback in `proc_seek()` by
adding an empty `.show` callback to `/proc/<pid>/mem`. That workaround was not
cherry-picked: it routes the entry through `generic_seek()`, which incorrectly
accepts `SEEK_END` using an empty generated-file size.

The semantic port adds an optional per-entry proc seek callback. The mem entry
uses the native Linux model: `SEEK_SET` replaces the raw signed 64-bit file
position, `SEEK_CUR` performs wrapping 64-bit addition, and `SEEK_END` or an
unknown `whence` returns `EINVAL` without changing the position. Other proc
files retain their generated-data refresh and size-based generic seek path.

`make test-arm64-proc-mem-seek` builds one static ARM64 fixture and runs
identical bytes first against the native AArch64 kernel and then under iSH. The
preserved fixture has SHA-256
`53ac766ed0303e25d8baddac8365110677177b36578114de1b9dbf1f31b9688e`.
Against the `v2.1.0` binary it exits 139 after a host SIGSEGV at address and PC
`0x0`; against the fixed binary it reports `proc-mem-seek-ok`. The matrix covers
positive and negative positions, the special `-1` raw-return case, arithmetic
wrap at both signed limits, rejected `SEEK_END`, and position preservation after
invalid requests.
