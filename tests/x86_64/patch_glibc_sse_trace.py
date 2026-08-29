#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

include_anchor = '''#include <string.h>\n'''
if '#include <stdio.h>\n' not in s:
    if include_anchor not in s:
        raise SystemExit("include anchor missing")
    s = s.replace(include_anchor, include_anchor + '#include <stdio.h>\n', 1)

anchor = '''            if (fetch_u8(cpu, ip + 1, &op2) < 0) goto gpf;\n\n'''
insert = r'''            if (op2 == 0x10) {
                uint8_t vmine_modrm = 0;
                fetch_u8(cpu, ip + 2, &vmine_modrm);
                fprintf(stderr,
                        "[vmine-0f10-dispatch] pc=%llx ip=%llx modrm=%02x rex=%02x op16=%d fs=%d\n",
                        (unsigned long long)cpu->pc,
                        (unsigned long long)ip,
                        vmine_modrm,
                        rex,
                        operand16 ? 1 : 0,
                        fs_prefix ? 1 : 0);
            }

'''
if anchor not in s:
    raise SystemExit("0F fetch anchor missing")
s = s.replace(anchor, anchor + insert, 1)
path.write_text(s)
print("patched x86_64 interpreter with temporary 0F10 dispatch trace")
