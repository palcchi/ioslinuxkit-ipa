#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 31: RDTSC. A synthetic monotonic timestamp counter is
            // sufficient for userspace loader timing/entropy probes. It is tied
            // to emulated instruction progress rather than wall clock time so
            // execution stays deterministic across hosts.
            if (op2 == 0x31) {
                uint64_t tsc = ((uint64_t)cpu->cycle << 10) + step;
                write_reg_bits(cpu, X86_64_RAX, (uint32_t)tsc, 32);
                write_reg_bits(cpu, X86_64_RDX, (uint32_t)(tsc >> 32), 32);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }

            // 0F 40..4F /r: CMOVcc r, r/m. CMOV is part of the ordinary
            // x86-64 baseline and glibc uses it heavily in early loader code.
            if (op2 >= 0x40 && op2 <= 0x4f) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (condition_true(cpu, op2 & 15)) {
                    uint64_t value;
                    if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
                    write_reg_bits(cpu, reg, value, bits);
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with RDTSC and CMOVcc")
