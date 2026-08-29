#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

old = '''        case 0x8: return false;                           // S? actually cc=8 is S
        case 0x9: return true;                            // NS
'''
new = '''        case 0x8: return cpu->nf;                         // S
        case 0x9: return !cpu->nf;                        // NS
'''
if old not in s:
    raise SystemExit("condition_true anchor missing")
s = s.replace(old, new, 1)

anchor = '''            // SYSCALL.\n'''
insert = r'''            // Minimal SSE/SSE2 data movement for the glibc loader. x86_64
            // guarantees SSE2, so even conservative loader startup code uses XMM.
            // 66 REX.W 0F 6E /r: MOVQ r/m64 -> xmm
            // 66       0F 6E /r: MOVD r/m32 -> xmm
            // 66 REX.W 0F 7E /r: MOVQ xmm -> r/m64
            // 66       0F 7E /r: MOVD xmm -> r/m32
            if (operand16 && (op2 == 0x6e || op2 == 0x7e)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                unsigned width = (rex & 0x8) ? 64 : 32;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (op2 == 0x6e) {
                    uint64_t value;
                    if (rm_read(cpu, &rm, width, &value) < 0) goto gpf;
                    cpu->xmm[xmm].u128 = 0;
                    cpu->xmm[xmm].u64[0] = value;
                } else {
                    uint64_t value = cpu->xmm[xmm].u64[0];
                    if (rm_write(cpu, &rm, width, value) < 0) goto gpf;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F 6C/6D /r: PUNPCKLQDQ/PUNPCKHQDQ.
            if (operand16 && (op2 == 0x6c || op2 == 0x6d)) {
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
                uint64_t old_lo = cpu->xmm[xmm].u64[0];
                uint64_t old_hi = cpu->xmm[xmm].u64[1];
                if (op2 == 0x6c) {
                    cpu->xmm[xmm].u64[0] = old_lo;
                    cpu->xmm[xmm].u64[1] = src.u64[0];
                } else {
                    cpu->xmm[xmm].u64[0] = old_hi;
                    cpu->xmm[xmm].u64[1] = src.u64[1];
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F 70 /r ib: PSHUFD xmm, xmm/m128, imm8.
            if (operand16 && op2 == 0x70) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src, dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                uint8_t imm;
                if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                for (unsigned lane = 0; lane < 4; lane++)
                    dst.u32[lane] = src.u32[(imm >> (lane * 2)) & 3];
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F EF /r: PXOR xmm, xmm/m128.
            if (operand16 && op2 == 0xef) {
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
                cpu->xmm[xmm].u128 ^= src.u128;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F 6F/7F: MOVDQA. F3 0F 6F/7F: MOVDQU. Alignment is
            // intentionally not trapped during bring-up; both copy 128 bits.
            if ((operand16 || rep_prefix) && (op2 == 0x6f || op2 == 0x7f)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (op2 == 0x6f) {
                    union x86_64_xmm value;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        value = cpu->xmm[rm.reg];
                    } else if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) {
                        goto gpf;
                    }
                    cpu->xmm[xmm] = value;
                } else {
                    union x86_64_xmm value = cpu->xmm[xmm];
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        cpu->xmm[rm.reg] = value;
                    } else if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) {
                        goto gpf;
                    }
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // F3 0F 7E /r: MOVQ xmm/m64 -> xmm (upper 64 bits zeroed).
            if (rep_prefix && !operand16 && op2 == 0x7e) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                uint64_t value;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    value = cpu->xmm[rm.reg].u64[0];
                } else if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) {
                    goto gpf;
                }
                cpu->xmm[xmm].u128 = 0;
                cpu->xmm[xmm].u64[0] = value;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 66 0F D6 /r: MOVQ xmm -> xmm/m64.
            if (operand16 && op2 == 0xd6) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                uint64_t value = cpu->xmm[xmm].u64[0];
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    cpu->xmm[rm.reg].u128 = 0;
                    cpu->xmm[rm.reg].u64[0] = value;
                } else if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) {
                    goto gpf;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // SETcc r/m8. Dynamic loaders love turning flag tests into bytes.
            if (op2 >= 0x90 && op2 <= 0x9f) {
                struct rm_operand rm;
                unsigned ignored;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &ignored, &next) < 0) goto gpf;
                uint64_t value = condition_true(cpu, op2 & 15) ? 1 : 0;
                if (rm_write(cpu, &rm, 8, value) < 0) goto gpf;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter for glibc SSE2 bring-up")
