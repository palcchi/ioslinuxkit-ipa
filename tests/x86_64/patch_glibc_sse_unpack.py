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

        // 0F 14/15: UNPCKLPS/UNPCKHPS, or with 66 mandatory
        // prefix UNPCKLPD/UNPCKHPD. These are bitwise lane transports.
        if (op == 0x0f && rep_prefix == 0) {
            uint8_t sseop;
            if (fetch_u8(cpu, ip + 1, &sseop) < 0) goto gpf;
            if (sseop == 0x14 || sseop == 0x15) {
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
                if (operand16) {
                    unsigned lane = sseop == 0x14 ? 0 : 1;
                    dst.u64[0] = old.u64[lane];
                    dst.u64[1] = src.u64[lane];
                } else {
                    unsigned lane = sseop == 0x14 ? 0 : 2;
                    dst.u32[0] = old.u32[lane];
                    dst.u32[1] = src.u32[lane];
                    dst.u32[2] = old.u32[lane + 1];
                    dst.u32[3] = src.u32[lane + 1];
                }
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

test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
func_anchor = '''static void test_write_exit(void) {\n'''
func = r'''static void test_sse_fp_unpack(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x66,0x0f,0x15,0xd1, // unpckhpd xmm2, xmm1
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.xmm[2].u64[0] = 0x1111111111111111ULL;
    cpu.xmm[2].u64[1] = 0x2222222222222222ULL;
    cpu.xmm[1].u64[0] = 0x3333333333333333ULL;
    cpu.xmm[1].u64[1] = 0x4444444444444444ULL;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(cpu.xmm[2].u64[0] == 0x2222222222222222ULL);
    assert(cpu.xmm[2].u64[1] == 0x4444444444444444ULL);
    puts("DIRECT X86_64 SSE FP UNPACK: PASS");
}

'''
if func_anchor not in t:
    raise SystemExit("SSE FP unpack function anchor missing")
t = t.replace(func_anchor, func + func_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("SSE FP unpack main anchor missing")
t = t.replace(main_anchor, '''    test_sse_fp_unpack();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 interpreter with integer and floating-point SSE unpack instructions")
