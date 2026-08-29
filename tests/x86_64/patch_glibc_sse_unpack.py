#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

# PUNPCKLQDQ/PUNPCKHQDQ are hit very early by Jammy's dynamic loader. Handle
# them immediately after prefix decoding, before the larger 0F dispatch. This
# deliberately avoids any interaction with the incremental 0F bring-up blocks.
early_anchor = '''        unsigned bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);\n'''
early_insert = r'''        // 66 0F 6C/6D: PUNPCKLQDQ/PUNPCKHQDQ. Keep this early
        // during bring-up so mandatory-prefix SSE2 qword unpack cannot be
        // intercepted by any of the generic incremental 0F handlers below.
        if (operand16 && op == 0x0f) {
            uint8_t sseop;
            if (fetch_u8(cpu, ip + 1, &sseop) < 0) goto gpf;
            if (sseop == 0x6c || sseop == 0x6d) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src, old, dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                old = cpu->xmm[xmm];
                dst.u128 = 0;
                unsigned base = sseop == 0x6c ? 0 : 1;
                dst.u64[0] = old.u64[base];
                dst.u64[1] = src.u64[base];
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
        }

'''
if early_anchor not in s:
    raise SystemExit("operand-size anchor missing")
s = s.replace(early_anchor, early_insert + early_anchor, 1)

anchor = '''            // SYSCALL.\n'''
insert = r'''            // 66 0F 60/61/62 and 68/69/6A: unpack/interleave packed
            // bytes, words and dwords. Qword unpack 6C/6D is handled earlier,
            // immediately after prefix decoding.
            if (operand16 &&
                (op2 == 0x60 || op2 == 0x61 || op2 == 0x62 ||
                 op2 == 0x68 || op2 == 0x69 || op2 == 0x6a)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src, old, dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                old = cpu->xmm[xmm];
                dst.u128 = 0;
                if (op2 == 0x60 || op2 == 0x68) {
                    unsigned base = op2 == 0x60 ? 0 : 8;
                    for (unsigned i = 0; i < 8; i++) {
                        dst.u8[i * 2] = old.u8[base + i];
                        dst.u8[i * 2 + 1] = src.u8[base + i];
                    }
                } else if (op2 == 0x61 || op2 == 0x69) {
                    unsigned base = op2 == 0x61 ? 0 : 4;
                    for (unsigned i = 0; i < 4; i++) {
                        dst.u16[i * 2] = old.u16[base + i];
                        dst.u16[i * 2 + 1] = src.u16[base + i];
                    }
                } else {
                    unsigned base = op2 == 0x62 ? 0 : 2;
                    for (unsigned i = 0; i < 2; i++) {
                        dst.u32[i * 2] = old.u32[base + i];
                        dst.u32[i * 2 + 1] = src.u32[base + i];
                    }
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
print("patched x86_64 interpreter with early qword and packed SSE2 unpack instructions")
