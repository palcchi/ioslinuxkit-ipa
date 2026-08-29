#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

old_sib = '''        if (mod == 0 && raw_base == 5 && !(rex & 0x1)) {\n'''
new_sib = '''        // In 64-bit mode, ModRM mod=00 + SIB base=101 is the special\n        // no-base disp32 form. REX.B does not turn this encoding into r13;\n        // [r13] must use mod=01/10 with a displacement.\n        if (mod == 0 && raw_base == 5) {\n'''

old_rip = '''    } else if (mod == 0 && raw_rm == 5 && !(rex & 0x1)) {\n'''
new_rip = '''    // Likewise, mod=00 r/m=101 remains RIP-relative in long mode.\n    // REX.B is ignored for this special encoding.\n    } else if (mod == 0 && raw_rm == 5) {\n'''

if old_sib not in s:
    raise SystemExit("SIB no-base anchor missing")
if old_rip not in s:
    raise SystemExit("RIP-relative anchor missing")

s = s.replace(old_sib, new_sib, 1)
s = s.replace(old_rip, new_rip, 1)
path.write_text(s)
print("patched x86_64 ModRM/SIB special base=5 semantics")
