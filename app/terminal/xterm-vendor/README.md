# Vendored xterm.js runtime

This directory contains the optional xterm.js renderer bundled with `ios-linuxkit`. Builds that include `app/XtermRenderer.xcconfig` load `xterm-term.html`; the default ARM64 app uses the Ghostty Web renderer.

Vendored packages:

- `@xterm/xterm` 6.0.0
- `@xterm/addon-attach` 0.12.0
- `@xterm/addon-canvas` 0.7.0
- `@xterm/addon-clipboard` 0.2.0
- `@xterm/addon-fit` 0.11.0
- `@xterm/addon-image` 0.9.0
- `@xterm/addon-ligatures` 0.10.0
- `@xterm/addon-progress` 0.2.0
- `@xterm/addon-search` 0.16.0
- `@xterm/addon-serialize` 0.14.0
- `@xterm/addon-unicode-graphemes` 0.4.0
- `@xterm/addon-unicode11` 0.9.0
- `@xterm/addon-web-links` 0.12.0
- `@xterm/addon-webgl` 0.19.0

All packages are MIT licensed by the xterm.js authors. `VENDORED.txt` records the source, date, bundle construction and renderer switch. [`LICENSES.md`](LICENSES.md) records the licence notice.
