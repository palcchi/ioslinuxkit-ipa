#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            if (op == 0x64) { fs_prefix = true; ip++; continue; }\n'''
insert = r'''            // ES/CS/SS/DS overrides have no address-base effect in 64-bit
            // mode. 2E/3E are also used as legacy branch-hint / CET NOTRACK
            // prefixes; CET is not advertised by this guest, so consume them.
            if (op == 0x26 || op == 0x2e || op == 0x36 || op == 0x3e) {
                ip++;
                continue;
            }
'''
if anchor not in s:
    raise SystemExit("legacy prefix anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with legacy segment-prefix handling")
