#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 54/55/56/57 /r: ANDPS/ANDNPS/ORPS/XORPS.
            // These are the prefix-less SSE bitwise logical forms. Do not
            // accept F2/F3-prefixed encodings here; 66-prefixed packed integer
            // variants are handled separately below.
            if (!operand16 && !rep_prefix &&
                (op2 == 0x54 || op2 == 0x55 || op2 == 0x56 || op2 == 0x57)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                if (op2 == 0x54)
                    cpu->xmm[xmm].u128 &= src.u128;
                else if (op2 == 0x55)
                    cpu->xmm[xmm].u128 = (~cpu->xmm[xmm].u128) & src.u128;
                else if (op2 == 0x56)
                    cpu->xmm[xmm].u128 |= src.u128;
                else
                    cpu->xmm[xmm].u128 ^= src.u128;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F DB/DF/EB /r: PAND/PANDN/POR. PXOR is handled by
            // the earlier SSE2 bring-up block. These packed logical operations
            // are pure 128-bit bitwise transforms, independent of lane type.
            if (operand16 && (op2 == 0xdb || op2 == 0xdf || op2 == 0xeb)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                if (op2 == 0xdb)
                    cpu->xmm[xmm].u128 &= src.u128;
                else if (op2 == 0xdf)
                    cpu->xmm[xmm].u128 = (~cpu->xmm[xmm].u128) & src.u128;
                else
                    cpu->xmm[xmm].u128 |= src.u128;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with SSE/SSE2 bitwise logic")
