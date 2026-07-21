# Documentation

The maintained documentation describes the current `master` branch. Dated evidence and superseded instructions are kept under `reports/` and `legacy/`.

## Maintained guides

| File | Subject |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | ARM64 decoder, gadget interpreter, memory model, userspace kernel and host boundaries. |
| [LINUX_DEVELOPMENT.md](LINUX_DEVELOPMENT.md) | AArch64 Linux build, fakefs, command-line use and diagnostics. |
| [IOS_APPLICATION.md](IOS_APPLICATION.md) | Xcode schemes, rootfs packaging, signing boundary and embedding interfaces. |
| [VALIDATION.md](VALIDATION.md) | Build and runtime gates, focused fixtures, reports and failure rules. |
| [LIMITATIONS.md](LIMITATIONS.md) | Security model, compatibility shims, incomplete facilities and unsupported workloads. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Source, test and documentation requirements for changes. |

## Reports

Reports record a result at a named date or revision. Paths, package versions and pass counts in these files may be obsolete.

| Directory | Contents |
|---|---|
| [reports/audits/](reports/audits/) | Source and upstream comparison audits. |
| [reports/benchmarks/game/](reports/benchmarks/game/) | Benchmarks Game harness and per-language results. |
| [reports/benchmarks/historical/](reports/benchmarks/historical/) | Retired x86/ARM64 compatibility and performance comparisons. |
| [reports/releases/](reports/releases/) | Previous production baseline and staging records. |
| [reports/workloads/](reports/workloads/) | Workload investigations such as `go-gte`. |

## Provenance

- [legacy/ORIGINAL_ISH_README_2026-05.md](legacy/ORIGINAL_ISH_README_2026-05.md) preserves the pre-rewrite fork README and its embedded upstream material.
- [legacy/](legacy/) also contains upstream translations and the superseded May 2026 Chinese backend guide.
- [SECURITY.md](../SECURITY.md) defines the security model.
- [LICENSE.md](../LICENSE.md) and [LICENSE.IOS](../LICENSE.IOS) contain licence terms.

Generated `fastlane/README.md` and executable `.pi/skills/*/SKILL.md` files are tool inputs, not project guides.
