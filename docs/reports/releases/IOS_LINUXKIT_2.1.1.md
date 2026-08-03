# ios-linuxkit 2.1.1 source release

> **Dated record — 3 August 2026:** This report applies to the source tagged `v2.1.1`. It records Linux-host validation, not an iOS archive or App Store upload.

## Version

- ARM64 marketing version: `2.1.1` in `app/AppARM64.xcconfig`
- Apple build number: `807` in all four project build configurations
- Source tag: annotated tag `v2.1.1`
- Release branch: `master` at the same commit as the tag

The inherited non-ARM64 version in `app/Project.xcconfig` remains `1.0.0`. Both shared ARM64 application schemes include `AppARM64.xcconfig` directly or through `AppARM64-ffmpeg.xcconfig`.

## Included fix

This compatible patch release ports the useful part of upstream iSH commit `297832fad03e318bcc10b9525da208902d5e9da7` (PR #2646) without inheriting its incorrect `SEEK_END` behaviour.

`/proc/<pid>/mem` now has an entry-specific seek callback. It accepts native Linux `SEEK_SET` and `SEEK_CUR` raw signed-offset semantics, including negative positions and 64-bit wrapping, and rejects `SEEK_END` or unknown origins with `EINVAL`. Generated proc files retain their existing refresh and size-based generic seek path.

## Regression evidence

`tests/arm64/proc/proc-mem-seek.c` is built once as a static AArch64 fixture and run byte-for-byte on the native kernel and under iSH. The preserved fixture SHA-256 is `53ac766ed0303e25d8baddac8365110677177b36578114de1b9dbf1f31b9688e`.

Against the existing `v2.1.0` release binary, that fixture produced:

```text
status=139
HOST CRASH: signal 11
fault addr: (nil)
pc: 0x0
```

Against the fixed release binary it reports `proc-mem-seek-ok`; the complete runner reports `proc-mem-seek-gate-ok`. The same focused gate is also run against the debug binary before tagging.

## Validation

Host: Orange Pi 6 Plus, CIX P1, Debian Trixie, AArch64, Clang 19.1.7.

Passed on 3 August 2026:

- clean Meson/Ninja release and debug builds from empty out-of-tree directories;
- `test-arm64-proc-mem-seek` against both clean binaries;
- the preserved pre-fix fixture bytes against the fixed release binary;
- `test-arm64-fcvt-vector` against both clean binaries;
- the supported default `CC=clang make build-arm64-linux-all` and `CC=clang make test-arm64-proc-mem-seek` flow;
- local links in all 38 Markdown files scanned by the checker;
- version consistency: ARM64 `2.1.1`, all four Apple build fields at `807`, inherited non-ARM64 version `1.0.0`;
- `git diff --check`.

The clean release binary SHA-256 is `d4fc347351a7803dc69901b29e72610efbd8604f4b6ffb662f9a54259da90568`; the clean debug binary SHA-256 is `fbcb40ee0a03edadad28518befcb98cc05e8c3faf1a1eb588a6020cf7a402a59`.

A Debian-only broad runtime attempt passed the shell, package-manager, temporary-file and symlink-retarget base rows, then stopped before C coverage when the existing platform detector selected Alpine package `build-base` despite the rootfs being Debian 13 with `build-essential` installed. This is recorded as a harness/package-bootstrap failure, not an emulator regression or pass for the unrun rows.

The builds retain existing Clang warnings, chiefly incompatible syscall function-pointer casts and unused helpers. No new warning was identified in the proc seek files.

## Validation boundary

This run does not build an Xcode archive, sign an application, install on a physical iOS device or upload to App Store Connect. The inherited Fastlane upload lane still targets upstream iSH.
