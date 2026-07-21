# OpenMinis `ish-arm64` audit — 2026-07-20

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
