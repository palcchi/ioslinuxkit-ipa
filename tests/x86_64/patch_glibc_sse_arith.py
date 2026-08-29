#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // Packed SSE2 integer add/subtract. glibc uses these while
            // manipulating feature masks and small vectorized tables during
            // dynamic-loader startup.
            // 66 0F F8/F9/FA/FB: PSUBB/W/D/Q
            // 66 0F FC/FD/FE:    PADDB/W/D
            // 66 0F D4:          PADDQ
            if (operand16 &&
                (op2 == 0xf8 || op2 == 0xf9 || op2 == 0xfa || op2 == 0xfb ||
                 op2 == 0xfc || op2 == 0xfd || op2 == 0xfe || op2 == 0xd4)) {
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
                    case 0xf8:
                        for (unsigned i = 0; i < 16; i++) dst.u8[i] = (uint8_t)(dst.u8[i] - src.u8[i]);
                        break;
                    case 0xf9:
                        for (unsigned i = 0; i < 8; i++) dst.u16[i] = (uint16_t)(dst.u16[i] - src.u16[i]);
                        break;
                    case 0xfa:
                        for (unsigned i = 0; i < 4; i++) dst.u32[i] = (uint32_t)(dst.u32[i] - src.u32[i]);
                        break;
                    case 0xfb:
                        for (unsigned i = 0; i < 2; i++) dst.u64[i] = dst.u64[i] - src.u64[i];
                        break;
                    case 0xfc:
                        for (unsigned i = 0; i < 16; i++) dst.u8[i] = (uint8_t)(dst.u8[i] + src.u8[i]);
                        break;
                    case 0xfd:
                        for (unsigned i = 0; i < 8; i++) dst.u16[i] = (uint16_t)(dst.u16[i] + src.u16[i]);
                        break;
                    case 0xfe:
                        for (unsigned i = 0; i < 4; i++) dst.u32[i] = dst.u32[i] + src.u32[i];
                        break;
                    case 0xd4:
                        for (unsigned i = 0; i < 2; i++) dst.u64[i] = dst.u64[i] + src.u64[i];
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
print("patched x86_64 interpreter with packed SSE2 integer arithmetic")
