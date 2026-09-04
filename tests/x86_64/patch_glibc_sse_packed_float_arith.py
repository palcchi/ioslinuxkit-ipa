#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
include_anchor = '''#include <string.h>\n'''
if include_anchor not in s:
    raise SystemExit("math include anchor missing")
s = s.replace(include_anchor, '''#include <string.h>
#include <math.h>
''', 1)
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 51: SQRTPS/SQRTPD/SQRTSS/SQRTSD.
            if (op2 == 0x51 &&
                (rep_prefix == 0 || rep_prefix == 0xf2 || rep_prefix == 0xf3)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src = {.u128 = 0}, dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                bool is_double = operand16 || rep_prefix == 0xf2;
                bool scalar = rep_prefix == 0xf2 || rep_prefix == 0xf3;
                size_t source_size = scalar ? (is_double ? 8 : 4) : 16;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, source_size) < 0) {
                    goto gpf;
                }
                dst = cpu->xmm[xmm];
                unsigned lanes = scalar ? 1 : (is_double ? 2 : 4);
                if (is_double) {
                    for (unsigned lane = 0; lane < lanes; lane++) {
                        double value, out;
                        memcpy(&value, &src.u64[lane], sizeof(value));
                        out = sqrt(value);
                        memcpy(&dst.u64[lane], &out, sizeof(out));
                    }
                } else {
                    for (unsigned lane = 0; lane < lanes; lane++) {
                        float value, out;
                        memcpy(&value, &src.u32[lane], sizeof(value));
                        out = sqrtf(value);
                        memcpy(&dst.u32[lane], &out, sizeof(out));
                    }
                }
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // F2/F3/66 0F E6: CVTPD2DQ, CVTDQ2PD, CVTTPD2DQ.
            if (op2 == 0xe6 &&
                (operand16 || rep_prefix == 0xf2 || rep_prefix == 0xf3)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src = {.u128 = 0}, dst = {.u128 = 0};
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                size_t source_size = rep_prefix == 0xf3 ? 8 : 16;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, source_size) < 0) {
                    goto gpf;
                }
                if (rep_prefix == 0xf3) {
                    for (unsigned lane = 0; lane < 2; lane++) {
                        double out = (double)(int32_t)src.u32[lane];
                        memcpy(&dst.u64[lane], &out, sizeof(out));
                    }
                } else {
                    for (unsigned lane = 0; lane < 2; lane++) {
                        double value;
                        memcpy(&value, &src.u64[lane], sizeof(value));
                        int32_t out = INT32_MIN;
                        if (isfinite(value) && value >= -2147483648.0 && value < 2147483648.0)
                            out = operand16 ? (int32_t)trunc(value) : (int32_t)nearbyint(value);
                        dst.u32[lane] = (uint32_t)out;
                    }
                }
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 0F 5B: packed integer/single-precision conversions.
            // CVTDQ2PS has no mandatory prefix; 66 selects CVTPS2DQ and F3
            // selects truncating CVTTPS2DQ.
            if (op2 == 0x5b && (rep_prefix == 0 || rep_prefix == 0xf3)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src = {.u128 = 0}, dst = {.u128 = 0};
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                if (!operand16 && rep_prefix == 0) {
                    for (unsigned lane = 0; lane < 4; lane++) {
                        float out = (float)(int32_t)src.u32[lane];
                        memcpy(&dst.u32[lane], &out, sizeof(out));
                    }
                } else {
                    for (unsigned lane = 0; lane < 4; lane++) {
                        float value;
                        memcpy(&value, &src.u32[lane], sizeof(value));
                        int32_t out = INT32_MIN;
                        if (isfinite(value) && value >= -2147483648.0f && value < 2147483648.0f)
                            out = rep_prefix == 0xf3 ? (int32_t)truncf(value) : (int32_t)nearbyintf(value);
                        dst.u32[lane] = (uint32_t)out;
                    }
                }
                cpu->xmm[xmm] = dst;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // Legacy packed SSE/SSE2 floating-point arithmetic.
            // No mandatory REP prefix means packed single precision; 66 selects
            // packed double precision. F2/F3 scalar forms are handled elsewhere.
            if (rep_prefix != 0xf2 && rep_prefix != 0xf3 &&
                (op2 == 0x58 || op2 == 0x59 || op2 == 0x5c || op2 == 0x5e)) {
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

                if (operand16) {
                    for (unsigned lane = 0; lane < 2; lane++) {
                        double a, b, out;
                        memcpy(&a, &cpu->xmm[xmm].u64[lane], sizeof(a));
                        memcpy(&b, &src.u64[lane], sizeof(b));
                        switch (op2) {
                            case 0x58: out = a + b; break;
                            case 0x59: out = a * b; break;
                            case 0x5c: out = a - b; break;
                            case 0x5e: out = a / b; break;
                            default: goto undefined;
                        }
                        memcpy(&cpu->xmm[xmm].u64[lane], &out, sizeof(out));
                    }
                } else {
                    for (unsigned lane = 0; lane < 4; lane++) {
                        float a, b, out;
                        memcpy(&a, &cpu->xmm[xmm].u32[lane], sizeof(a));
                        memcpy(&b, &src.u32[lane], sizeof(b));
                        switch (op2) {
                            case 0x58: out = a + b; break;
                            case 0x59: out = a * b; break;
                            case 0x5c: out = a - b; break;
                            case 0x5e: out = a / b; break;
                            default: goto undefined;
                        }
                        memcpy(&cpu->xmm[xmm].u32[lane], &out, sizeof(out));
                    }
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
interp.write_text(s)

test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_packed_double_int_conversion(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x66,0x0f,0xe6,0xc8,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    const double input[2] = {42.75, -7.9};
    memcpy(cpu.xmm[0].u64, input, sizeof(input));
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert((int32_t)cpu.xmm[1].u32[0] == 42);
    assert((int32_t)cpu.xmm[1].u32[1] == -7);
    assert(cpu.xmm[1].u64[1] == 0);
    puts("DIRECT X86_64 PACKED DOUBLE CONVERSION: PASS");
}

static void test_packed_int_float_conversion(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x0f,0x5b,0xc9,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    const int32_t input[4] = {1, -2, 16777216, 42};
    memcpy(cpu.xmm[1].u32, input, sizeof(input));
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    const float expected[4] = {1.0f, -2.0f, 16777216.0f, 42.0f};
    for (unsigned lane = 0; lane < 4; lane++) {
        uint32_t raw;
        memcpy(&raw, &expected[lane], sizeof(raw));
        assert(cpu.xmm[1].u32[lane] == raw);
    }
    puts("DIRECT X86_64 PACKED CONVERSION: PASS");
}

static void test_packed_sse_float_arith(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x0f,0x59,0xdc,             // MULPS xmm3, xmm4
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    const float lhs[4] = {1.0f, 2.0f, -3.0f, 4.0f};
    const float rhs[4] = {5.0f, -2.0f, 0.5f, 3.0f};
    const float expected[4] = {5.0f, -4.0f, -1.5f, 12.0f};
    memcpy(cpu.xmm[3].u32, lhs, sizeof(lhs));
    memcpy(cpu.xmm[4].u32, rhs, sizeof(rhs));
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    for (unsigned lane = 0; lane < 4; lane++) {
        uint32_t raw;
        memcpy(&raw, &expected[lane], sizeof(raw));
        assert(cpu.xmm[3].u32[lane] == raw);
    }
    puts("DIRECT X86_64 PACKED SSE FLOAT ARITH: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
main_replace = '''    test_packed_double_int_conversion();\n    test_packed_int_float_conversion();\n    test_packed_sse_float_arith();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 SSE square roots and packed floating-point arithmetic")
