#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
if '#include <stdio.h>' not in s:
    s = s.replace('#include <string.h>\n', '#include <string.h>\n#include <stdio.h>\n', 1)

anchor = '''        // 66 0F 6C/6D: PUNPCKLQDQ/PUNPCKHQDQ. Keep this early\n'''
insert = r'''        // Temporary prefix-state diagnostic for the Jammy loader's
        // 66 0F 6C C4 frontier. Read from architectural instruction start so
        // this still fires even if prefix parsing left ip/op in a bad state.
        {
            uint8_t pb0 = 0, pb1 = 0, pb2 = 0, pb3 = 0;
            if (fetch_u8(cpu, insn_start, &pb0) == 0 &&
                fetch_u8(cpu, insn_start + 1, &pb1) == 0 &&
                fetch_u8(cpu, insn_start + 2, &pb2) == 0 &&
                fetch_u8(cpu, insn_start + 3, &pb3) == 0 &&
                pb0 == 0x66 && pb1 == 0x0f && (pb2 == 0x6c || pb2 == 0x6d)) {
                fprintf(stderr,
                        "[x86-sse-prefix] pc=%llx ip=%llx raw=%02x%02x%02x%02x op=%02x operand16=%d rep=%d rex=%02x\\n",
                        (unsigned long long)insn_start,
                        (unsigned long long)ip,
                        pb0, pb1, pb2, pb3, op,
                        operand16 ? 1 : 0, rep_prefix ? 1 : 0, rex);
            }
        }

'''
if anchor not in s:
    raise SystemExit("early qword SSE anchor missing")
s = s.replace(anchor, insert + anchor, 1)
p.write_text(s)
print("patched x86_64 interpreter with SSE mandatory-prefix trace")
