#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 2E/2F /r: UCOMISS/COMISS xmm, xmm/m32.
            // 66 0F 2E/2F /r: UCOMISD/COMISD xmm, xmm/m64.
            // COMI and UCOMI differ in which NaNs raise an unmasked SIMD
            // exception. MXCSR exceptions are not modeled yet, but their
            // architectural ZF/PF/CF comparison results are the same.
            if (!rep_prefix && (op2 == 0x2e || op2 == 0x2f)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;

                bool unordered = false;
                bool less = false;
                bool equal = false;
                if (operand16) {
                    uint64_t lhs_raw = cpu->xmm[xmm].u64[0];
                    uint64_t rhs_raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        rhs_raw = cpu->xmm[rm.reg].u64[0];
                    } else if (guest_read(cpu, rm.addr, &rhs_raw, sizeof(rhs_raw)) < 0) {
                        goto gpf;
                    }
                    bool lhs_nan = (lhs_raw & 0x7ff0000000000000ULL) == 0x7ff0000000000000ULL &&
                                   (lhs_raw & 0x000fffffffffffffULL) != 0;
                    bool rhs_nan = (rhs_raw & 0x7ff0000000000000ULL) == 0x7ff0000000000000ULL &&
                                   (rhs_raw & 0x000fffffffffffffULL) != 0;
                    unordered = lhs_nan || rhs_nan;
                    if (!unordered) {
                        double lhs, rhs;
                        memcpy(&lhs, &lhs_raw, sizeof(lhs));
                        memcpy(&rhs, &rhs_raw, sizeof(rhs));
                        less = lhs < rhs;
                        equal = lhs == rhs;
                    }
                } else {
                    uint32_t lhs_raw = cpu->xmm[xmm].u32[0];
                    uint32_t rhs_raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        rhs_raw = cpu->xmm[rm.reg].u32[0];
                    } else if (guest_read(cpu, rm.addr, &rhs_raw, sizeof(rhs_raw)) < 0) {
                        goto gpf;
                    }
                    bool lhs_nan = (lhs_raw & 0x7f800000U) == 0x7f800000U &&
                                   (lhs_raw & 0x007fffffU) != 0;
                    bool rhs_nan = (rhs_raw & 0x7f800000U) == 0x7f800000U &&
                                   (rhs_raw & 0x007fffffU) != 0;
                    unordered = lhs_nan || rhs_nan;
                    if (!unordered) {
                        float lhs, rhs;
                        memcpy(&lhs, &lhs_raw, sizeof(lhs));
                        memcpy(&rhs, &rhs_raw, sizeof(rhs));
                        less = lhs < rhs;
                        equal = lhs == rhs;
                    }
                }

                // Intel COMI/UCOMI result table:
                // unordered: ZF=PF=CF=1; greater: all 0;
                // less: CF=1; equal: ZF=1. OF/SF/AF are cleared.
                cpu->vf = 0;
                cpu->nf = 0;
                if (unordered) {
                    cpu->zf = 1;
                    cpu->pf = 1;
                    cpu->cf = 1;
                } else {
                    cpu->zf = equal;
                    cpu->pf = 0;
                    cpu->cf = less;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F 74/75/76 /r: PCMPEQB/W/D xmm, xmm/m128.
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
print("patched x86_64 interpreter with packed and scalar SSE compares")
