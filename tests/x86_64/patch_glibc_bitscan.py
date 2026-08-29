#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F BC/BD /r: BSF/BSR r, r/m. glibc uses bit scans while
            // turning its CPU feature bitmap into dispatch choices.
            if (op2 == 0xbc || op2 == 0xbd) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                unsigned scan_bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);
                uint64_t value;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, scan_bits, &value) < 0) goto gpf;
                value &= bits_mask(scan_bits);
                if (value == 0) {
                    cpu->zf = 1;
                    // Destination is architecturally undefined. Leaving it
                    // unchanged is deterministic and sufficient for callers
                    // that correctly branch on ZF.
                } else {
                    cpu->zf = 0;
                    unsigned index;
                    if (op2 == 0xbc) {
                        index = (unsigned)__builtin_ctzll(value);
                    } else {
                        index = 63u - (unsigned)__builtin_clzll(value);
                    }
                    write_reg_bits(cpu, reg, index, scan_bits);
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
print("patched x86_64 interpreter with BSF/BSR")
