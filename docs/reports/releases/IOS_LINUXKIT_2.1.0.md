# ios-linuxkit 2.1.0 source release

> **Dated record — 31 July 2026:** This report applies to the source tagged `v2.1.0`. It records Linux-host validation, not an iOS archive or App Store upload.

## Version

- ARM64 marketing version: `2.1.0` in `app/AppARM64.xcconfig`
- Apple build number: `806` in all four project build configurations
- Source tag: annotated tag `v2.1.0`
- Release branch: `master` at the same commit as the tag

The inherited non-ARM64 version in `app/Project.xcconfig` remains `1.0.0`. Both shared ARM64 application schemes include `AppARM64.xcconfig` directly or through `AppARM64-ffmpeg.xcconfig`.

The older `v2.0.0` tag points to the divergent OpenMinis release commit and is not an ancestor of this branch. It remains unchanged for provenance.

## Included work

This source release includes:

- the 31 correctness imports recorded in the [20 July OpenMinis audit](../audits/OPENMINIS_AUDIT_2026-07-20.md);
- ARM64 `FCVTN`/`FCVTN2` and `FCVTXN`/`FCVTXN2`, precise `FCVTL` decoding, guest `FPCR`/`FPSR` handling and the native-oracle/guest fixture from `40f1bf40`;
- the maintained architecture, Linux, iOS, validation, limitations, contribution and release guides;
- corrected fork-specific security reporting, issue diagnostics, xterm provenance and local debugging paths.

## Validation

Host: Orange Pi 6 Plus, CIX P1, Debian Trixie, AArch64, Clang 19.1.7.

Passed on 31 July 2026:

- clean Meson/Ninja release build: 96 / 96 steps;
- clean Meson/Ninja debug build: 96 / 96 steps;
- `test-arm64-fcvt-vector` against both clean binaries;
- realfs smoke: `/bin/echo hello`, exit status `0`;
- local links in all 44 tracked Markdown files scanned by the checker;
- 30 distinct external HTTP URLs and the published maintainer email link;
- XML parsing for application, File Provider and UI test property lists and all shared Xcode schemes;
- version consistency: ARM64 `2.1.0`, four Apple build fields at `806`;
- `git diff --check`.

The builds retain existing Clang warnings, chiefly incompatible syscall function-pointer casts and unused helper functions. This documentation/version change introduced no C or assembly source changes.

## Validation boundary

This run did not build an Xcode archive, sign an application, install on a physical iOS device or upload to App Store Connect. The inherited Fastlane upload lane still targets upstream iSH.

The broad package/runtime suite was not rerun for this documentation and version change. Its latest repository-wide results remain those attached to the revisions in the [OpenMinis audit](../audits/OPENMINIS_AUDIT_2026-07-20.md). Package-manager bootstrap and live repositories are separate dependencies of that suite.
