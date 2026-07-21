# Validation

Every runtime change needs a focused regression and a broader gate. The Makefile records the supported Linux-host workflows; each script writes a Markdown report under `REPORT_DIR`.

## Host and test data

The maintained gates run on an AArch64 Linux host. The July 2026 audit used an Orange Pi 6 Plus with a CIX P1 SoC, Debian Trixie and Clang 19.1.7.

Runtime tests modify their fakefs when they install missing packages. Copy the rootfs or rebuild it when package state must be reproducible. Network and package repositories can make broad suites non-deterministic even when the emulator is unchanged.

## Build gate

```sh
CC=clang make build-arm64-linux-all
```

This builds release and debug variants. Treat compiler errors, assembler errors and warnings introduced by the change as failures.

## Runtime gates

| Gate | Command | Scope |
|---|---|---|
| Release runtime | `make test-arm64-runtime-coverage` | Shell, package manager, C fixtures and language runtimes. |
| Debug runtime | `make test-arm64-runtime-coverage-debug` | Same suite with the debug binary. |
| CLI corner cases | `make test-arm64-cli-corner-smoke` | TUI, DNS, HTTPS, Git, Docker probes and command-line packages. |
| npm CLI packages | `make test-arm64-npm-cli-runtime-coverage` | Moving npm CLI install and startup paths. |
| Multi-manager CLI packages | `make test-arm64-cli-package-runtime-coverage` | npm, Bun and pip lanes selected by `CLI_PACKAGE_MANAGERS`. |
| Internal continue | `make test-arm64-internal-continue-fixtures` | Opt-in executor path and first-call-site fixtures. |
| Node/Bun timing | `make test-arm64-node-bun-perf` | Before-and-after timing and optional executor counters. |
| Pinned performance | `make perf-bench` | Repeated pinned workloads with percentile output. |

Useful parameters are defined at the top of `Makefile`:

```sh
make test-arm64-runtime-coverage \
  ROOTFS_LANES="alpine=$PWD/alpine-arm64-fakefs" \
  REPORT_DIR=/workspace/tmp \
  TIMEOUT_S=180 \
  INSTALL_TIMEOUT_S=1200
```

The default `ROOTFS_LANES` includes both Alpine and Debian. Override it when only one prepared rootfs exists. The Debian target can create `debian-arm64-fakefs`, but it uses `sudo debootstrap`, downloads packages and deletes its temporary output directories; inspect the Makefile recipe before running it.

Cold Go caches can exceed the ordinary timeout because Alpine may ship standard-library source without precompiled archives. Increase `TIMEOUT_S` for a cold toolchain instead of classifying a harness kill as a pass.

## Runtime coverage stages

`tests/arm64/runtime-coverage.sh` currently checks:

- shell startup, package-manager access, temporary files and symlink retargeting;
- C compilation and execution;
- SysV and POSIX IPC, modern syscall probes, sockets and fd passing;
- ARM64 faults, signal context, barriers, self-modifying code and fused load/store paths;
- Go build, run and test;
- Bun install, TypeScript, test and build;
- Node/npm startup and scripts;
- Python, Lua, Java, Clojure, Rust, Erlang and Zig paths;
- explicit availability results for optional toolchains.

Read the script for the exact current rows. A number in a dated report applies only to that script revision, binary, rootfs and package state.

## Focused instruction fixtures

Standalone source fixtures live under:

```text
tests/arm64/atomics/
tests/arm64/loadstore/
tests/arm64/signals/
```

They cover CAS pairs, exclusive monitor clearing, exclusive widths, pair exclusives, `LDPSW` and per-thread alternate signal stacks. New instruction work should add a similarly small fixture and include it in a repeatable script or runtime row.

A focused fixture should test architectural edge cases relevant to the instruction:

- all implemented operand widths and vector arrangements;
- source and destination register aliasing;
- upper-lane preservation or zeroing;
- condition flags and rounding modes;
- alignment and cross-page accesses;
- faults and reserved encodings.

## Failure rules

A row fails when any of these occur:

1. the command exits non-zero;
2. the harness reaches its timeout or kills the process;
3. `SAFETY-VALVE` appears in a non-diagnostic row;
4. unexpected fault, illegal-instruction or `NETDIAG` output appears;
5. a required row is skipped or silently reported as success;
6. the expected output came from stale artefacts rather than the binary built for the run.

Unsupported facilities must be reported as unsupported with a reason. Package absence and rootfs packaging errors are not emulator passes; record them separately from instruction or syscall results.

## Diagnostics during tests

`ISH_ARM64_BLOCK_STATS=1` and `ISH_ARM64_FUSION_STATS=1` intentionally add output. Use them for performance investigations, not exact-output correctness gates. Fault and PC tracing can also perturb timing and produce large logs.

When a broad row fails, rerun its exact guest command with a bounded timeout. Preserve:

- source revision and dirty-tree state;
- release or debug binary path and checksum when needed;
- rootfs name and relevant package versions;
- complete command and environment;
- exit status and diagnostic excerpt.

## Current evidence

The latest repository-wide upstream audit is [`reports/audits/OPENMINIS_AUDIT_2026-07-20.md`](reports/audits/OPENMINIS_AUDIT_2026-07-20.md). At commit `35dac743` it records:

- Clang release and debug builds passing;
- all 47 C/ARM64 runtime checks passing;
- focused atomic, timer, epoll, `madvise`, signal and pidfd regressions passing;
- two broad release runs at 82/83, with a transient Go result passing on retry and the remaining Clojure failure attributed to the tested rootfs package layout.

Older reports under `reports/` remain useful evidence for the code and environment they name. They do not override a later failed gate.

## Before commit

Run at least:

```sh
CC=clang make build-arm64-linux-all
git diff --check
git status --short
```

Run the focused regression and the release runtime gate for behavioural changes. Use the debug gate for memory, signal, concurrency and translated-execution changes. Check Markdown links after moving documentation.
