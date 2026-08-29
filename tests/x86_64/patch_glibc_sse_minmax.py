#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // SSE2 packed integer min/max forms used by glibc vectorized
            // string/table routines.
            // 66 0F DA: PMINUB  unsigned byte minimum
            // 66 0F DE: PMAXUB  unsigned byte maximum
            // 66 0F EA: PMINSW  signed word minimum
            // 66 0F EE: PMAXSW  signed word maximum
            if (operand16 &&
                (op2 == 0xda || op2 == 0xde || op2 == 0xea || op2 == 0xee)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src, dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                dst = cpu->xmm[xmm];
                switch (op2) {
                    case 0xda:
                        for (unsigned i = 0; i < 16; i++)
                            if (src.u8[i] < dst.u8[i]) dst.u8[i] = src.u8[i];
                        break;
                    case 0xde:
                        for (unsigned i = 0; i < 16; i++)
                            if (src.u8[i] > dst.u8[i]) dst.u8[i] = src.u8[i];
                        break;
                    case 0xea:
                        for (unsigned i = 0; i < 8; i++) {
                            int16_t a = (int16_t)dst.u16[i];
                            int16_t b = (int16_t)src.u16[i];
                            if (b < a) dst.u16[i] = src.u16[i];
                        }
                        break;
                    case 0xee:
                        for (unsigned i = 0; i < 8; i++) {
                            int16_t a = (int16_t)dst.u16[i];
                            int16_t b = (int16_t)src.u16[i];
                            if (b > a) dst.u16[i] = src.u16[i];
                        }
                        break;
                }
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with SSE2 packed min/max")
