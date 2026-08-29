#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 66 0F 74/75/76 /r: PCMPEQB/W/D xmm, xmm/m128.
            // 66 0F 64/65/66 /r: PCMPGTB/W/D xmm, xmm/m128.
            if (operand16 &&
                (op2 == 0x74 || op2 == 0x75 || op2 == 0x76 ||
                 op2 == 0x64 || op2 == 0x65 || op2 == 0x66)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src, dst = cpu->xmm[0];
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                dst.u128 = 0;
                if (op2 == 0x74 || op2 == 0x64) {
                    for (unsigned lane = 0; lane < 16; lane++) {
                        bool yes = op2 == 0x74
                            ? cpu->xmm[xmm].u8[lane] == src.u8[lane]
                            : (int8_t)cpu->xmm[xmm].u8[lane] > (int8_t)src.u8[lane];
                        dst.u8[lane] = yes ? UINT8_MAX : 0;
                    }
                } else if (op2 == 0x75 || op2 == 0x65) {
                    for (unsigned lane = 0; lane < 8; lane++) {
                        bool yes = op2 == 0x75
                            ? cpu->xmm[xmm].u16[lane] == src.u16[lane]
                            : (int16_t)cpu->xmm[xmm].u16[lane] > (int16_t)src.u16[lane];
                        dst.u16[lane] = yes ? UINT16_MAX : 0;
                    }
                } else {
                    for (unsigned lane = 0; lane < 4; lane++) {
                        bool yes = op2 == 0x76
                            ? cpu->xmm[xmm].u32[lane] == src.u32[lane]
                            : (int32_t)cpu->xmm[xmm].u32[lane] > (int32_t)src.u32[lane];
                        dst.u32[lane] = yes ? UINT32_MAX : 0;
                    }
                }
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F D7 /r: PMOVMSKB r32, xmm. The source is register-only.
            if (operand16 && op2 == 0xd7) {
                struct rm_operand rm;
                unsigned gpr;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &gpr, &next) < 0) goto gpf;
                if (!rm.is_reg || rm.reg >= 16 || gpr >= 16) goto undefined;
                uint32_t mask = 0;
                for (unsigned lane = 0; lane < 16; lane++)
                    mask |= ((uint32_t)(cpu->xmm[rm.reg].u8[lane] >> 7) & 1u) << lane;
                write_reg_bits(cpu, gpr, mask, 32);
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with packed SSE2 compares")
