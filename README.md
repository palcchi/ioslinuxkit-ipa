# V-MINE

**V-MINE** is the BDS-focused iOS/iPadOS direction of this branch. It uses the project's direct x86_64 guest runtime to run Mojang's official Linux Bedrock Dedicated Server on ARM64 iOS hardware, while presenting a native server-management UI instead of a general Linux terminal.

The target product covers server install/update from official Minecraft/Mojang sources, Start/Stop, console, world management, backups, player management and `server.properties` settings. See [`docs/V-MINE.md`](docs/V-MINE.md) for the product/runtime plan.

V-MINE is an independent project and is not affiliated with or endorsed by Mojang Studios or Microsoft.

## Runtime foundation

![ios-linuxkit icon](docs/icon-256.png)

The runtime derives from `ios-linuxkit`/iSH and uses iSH's userspace kernel, filesystems and Asbestos threaded-code interpreter. The `x86_64-guest` branch extends that foundation with a direct x86_64 compatibility path aimed first at Bedrock Dedicated Server rather than general-purpose x86_64 Linux compatibility.

The current source version is **2.1.1** with Apple build number **807**. The existing ARM64 runtime remains the stable foundation while the BDS-focused x86_64 compatibility work is developed on this branch.

## What is in the repository

- the existing ARM64 instruction decoder and AArch64 host gadgets under `asbestos/guest-arm64/`;
- the developing direct x86_64 guest compatibility path used by V-MINE;
- a 48-bit guest address space, Linux syscall layer, signals, sockets and fakefs;
- the iOS application host and terminal frontend inherited from the runtime project;
- Linux-host builds for development and regression testing;
- staged tests for instructions, syscalls, dynamic glibc programs and Bedrock Dedicated Server compatibility.

The outer iOS sandbox is the security boundary; read [SECURITY.md](SECURITY.md) before embedding the runtime or exposing guest workloads to untrusted input.

## V-MINE compatibility target

The BDS runtime is considered complete only when the official server can start, create/load a world, listen on its Bedrock UDP port, accept a client, save correctly, process console commands and stop cleanly. Compatibility work should prioritize instructions and Linux behavior actually exercised by BDS instead of attempting to support arbitrary x86_64 desktop software.

## Quick start on AArch64 Linux

Install Clang, Meson, Ninja, pkg-config, SQLite development files and libarchive development files. On Debian or Ubuntu:

```sh
sudo apt install \
  clang make meson ninja-build pkg-config git curl file tar \
  libsqlite3-dev libarchive-dev
```

Clone the submodules and build:

```sh
git clone --recurse-submodules https://github.com/rcarmo/ios-linuxkit.git
cd ios-linuxkit
make build-arm64-linux
```

Run against the host filesystem:

```sh
./build-arm64-linux/ish -r / /bin/echo hello
```

To create an Alpine fakefs, download the root filesystem named in `app/GuestARM64.xcconfig`, then import it:

```sh
curl -LO https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/alpine-minirootfs-3.24.0-aarch64.tar.gz
./build-arm64-linux/tools/fakefsify \
  alpine-minirootfs-3.24.0-aarch64.tar.gz \
  alpine-arm64-fakefs
./build-arm64-linux/ish -f ./alpine-arm64-fakefs /bin/sh
```

`fakefsify` is built when Meson finds libarchive. Existing build directories retain their original Meson configuration; remove or reconfigure them when changing the compiler or build type.

## Build and test commands

| Task | Command |
|---|---|
| Build release | `make build-arm64-linux` |
| Build release and debug | `make build-arm64-linux-all` |
| Check documentation links | `make check-docs` |
| Test AdvSIMD FP widening and narrowing | `CC=clang make test-arm64-fcvt-vector` |
| Test `/proc/<pid>/mem` seek semantics | `CC=clang make test-arm64-proc-mem-seek` |
| Run staged runtime coverage | `make test-arm64-runtime-coverage` |
| Run coverage with the debug binary | `make test-arm64-runtime-coverage-debug` |
| Run CLI corner cases | `make test-arm64-cli-corner-smoke` |
| Run npm CLI coverage | `make test-arm64-npm-cli-runtime-coverage` |
| Measure Node and Bun | `make test-arm64-node-bun-perf` |

The runtime and CLI targets can install packages into their fakefs. Use a disposable copy when package state matters. Reports are written to `REPORT_DIR`, which defaults to `/workspace/tmp`.

## Documentation

| Document | Use it for |
|---|---|
| [V-MINE plan](docs/V-MINE.md) | BDS-only product scope, runtime target, update flow and native UI. |
| [Documentation index](docs/README.md) | Choosing the maintained guide or dated report. |
| [Architecture](docs/ARCHITECTURE.md) | Interpreter, memory, kernel and host boundaries. |
| [Linux development](docs/LINUX_DEVELOPMENT.md) | Building, fakefs creation, command-line use and diagnostics. |
| [iOS application](docs/IOS_APPLICATION.md) | Xcode schemes, rootfs packaging and host integration. |
| [Validation](docs/VALIDATION.md) | Test gates, reports and failure rules. |
| [Limitations](docs/LIMITATIONS.md) | Security, compatibility and unsupported workloads. |
| [Contributing](docs/CONTRIBUTING.md) | Change and documentation requirements. |
| [Versioning and releases](docs/RELEASES.md) | App versions, build numbers, Git tags and release checks. |

Dated benchmark, workload, release and audit records live under [`docs/reports/`](docs/reports/). They preserve their original observations and are not current operating instructions.

## Licence and provenance

V-MINE's runtime contains work derived from [ish-app/ish](https://github.com/ish-app/ish), ios-linuxkit and their dependencies. See [LICENSE.md](LICENSE.md), [LICENSE.IOS](LICENSE.IOS), the [preserved May 2026 README](docs/legacy/ORIGINAL_ISH_README_2026-05.md), and [`docs/legacy/`](docs/legacy/).
