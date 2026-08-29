#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // F3 [REX.W] 0F 1E /1: RDSSPD/RDSSPQ. Our conservative
            // CPUID model does not advertise CET shadow stacks. On x86, RDSSP
            // is effectively a no-op when shadow stacks are disabled, leaving
            // the destination unchanged. glibc deliberately zeroes the target
            // register first and uses the resulting zero to skip CET restore
            // machinery, so preserve that architectural behavior here.
            if (rep_prefix && op2 == 0x1e) {
                uint8_t modrm;
                if (fetch_u8(cpu, ip + 2, &modrm) < 0) goto gpf;
                if (((modrm >> 3) & 7) == 1 && (modrm >> 6) == 3) {
                    cpu->pc = ip + 3;
                    cpu->cycle++;
                    continue;
                }
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with CET-disabled RDSSP behavior")
