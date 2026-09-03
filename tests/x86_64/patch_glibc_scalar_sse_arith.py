#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // Scalar SSE/SSE2 arithmetic. F3 selects float, F2 selects double.
            // 0F 58: ADDSS/ADDSD, 0F 59: MULSS/MULSD,
            // 0F 5C: SUBSS/SUBSD, 0F 5D: MINSS/MINSD,
            // 0F 5E: DIVSS/DIVSD, 0F 5F: MAXSS/MAXSD.
            // Only the low scalar lane changes; upper destination bits survive.
            if ((rep_prefix == 0xf3 || rep_prefix == 0xf2) &&
                (op2 == 0x58 || op2 == 0x59 || op2 == 0x5c || op2 == 0x5d ||
                 op2 == 0x5e || op2 == 0x5f)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                uint64_t src_raw;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src_raw = rep_prefix == 0xf3 ? cpu->xmm[rm.reg].u32[0] : cpu->xmm[rm.reg].u64[0];
                } else if (rep_prefix == 0xf3) {
                    uint32_t src32;
                    if (guest_read(cpu, rm.addr, &src32, sizeof(src32)) < 0) goto gpf;
                    src_raw = src32;
                } else {
                    if (guest_read(cpu, rm.addr, &src_raw, sizeof(src_raw)) < 0) goto gpf;
                }

                if (rep_prefix == 0xf3) {
                    uint32_t dst_raw = cpu->xmm[xmm].u32[0];
                    uint32_t src32 = (uint32_t)src_raw;
                    float dst, srcv, out;
                    memcpy(&dst, &dst_raw, sizeof(dst));
                    memcpy(&srcv, &src32, sizeof(srcv));
                    switch (op2) {
                        case 0x58: out = dst + srcv; break;
                        case 0x59: out = dst * srcv; break;
                        case 0x5c: out = dst - srcv; break;
                        // Legacy MIN/MAX select the source for equal values
                        // (including signed zero) and for unordered compares.
                        case 0x5d: out = dst < srcv ? dst : srcv; break;
                        case 0x5e: out = dst / srcv; break;
                        case 0x5f: out = dst > srcv ? dst : srcv; break;
                        default: goto undefined;
                    }
                    memcpy(&cpu->xmm[xmm].u32[0], &out, sizeof(out));
                } else {
                    uint64_t dst_raw = cpu->xmm[xmm].u64[0];
                    double dst, srcv, out;
                    memcpy(&dst, &dst_raw, sizeof(dst));
                    memcpy(&srcv, &src_raw, sizeof(srcv));
                    switch (op2) {
                        case 0x58: out = dst + srcv; break;
                        case 0x59: out = dst * srcv; break;
                        case 0x5c: out = dst - srcv; break;
                        // Legacy MIN/MAX select the source for equal values
                        // (including signed zero) and for unordered compares.
                        case 0x5d: out = dst < srcv ? dst : srcv; break;
                        case 0x5e: out = dst / srcv; break;
                        case 0x5f: out = dst > srcv ? dst : srcv; break;
                        default: goto undefined;
                    }
                    memcpy(&cpu->xmm[xmm].u64[0], &out, sizeof(out));
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

# Exact BDS frontier plus double and memory-source regressions.
test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_scalar_sse_arith(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    uint32_t fraw;
    uint64_t draw;

    // Exact BDS frontier: F3 0F 5E C1 = DIVSS xmm0, xmm1.
    memset(memory, 0, sizeof(memory));
    const uint8_t divss_program[] = {
        0xf3,0x0f,0x5e,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, divss_program, sizeof(divss_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    float nine = 9.0f, three = 3.0f, expected_f = 3.0f;
    memcpy(&cpu.xmm[0].u32[0], &nine, sizeof(nine));
    memcpy(&cpu.xmm[1].u32[0], &three, sizeof(three));
    cpu.xmm[0].u32[1] = 0x11223344U;
    cpu.xmm[0].u64[1] = 0x5566778899aabbccULL;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    memcpy(&fraw, &expected_f, sizeof(fraw));
    assert(cpu.xmm[0].u32[0] == fraw);
    assert(cpu.xmm[0].u32[1] == 0x11223344U);
    assert(cpu.xmm[0].u64[1] == 0x5566778899aabbccULL);

    // Exact current BDS frontier: MAXSS xmm0, xmm1.
    memset(memory, 0, sizeof(memory));
    const uint8_t maxss_program[] = {
        0xf3,0x0f,0x5f,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, maxss_program, sizeof(maxss_program));
    cpu = fresh_cpu(&mmu);
    float minus_two = -2.0f, five = 5.0f;
    memcpy(&cpu.xmm[0].u32[0], &minus_two, sizeof(minus_two));
    memcpy(&cpu.xmm[1].u32[0], &five, sizeof(five));
    cpu.xmm[0].u64[1] = 0xcafebabedeadbeefULL;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    memcpy(&fraw, &five, sizeof(fraw));
    assert(cpu.xmm[0].u32[0] == fraw);
    assert(cpu.xmm[0].u64[1] == 0xcafebabedeadbeefULL);

    // F2 path: ADDSD xmm0, xmm1, preserving the upper qword.
    memset(memory, 0, sizeof(memory));
    const uint8_t addsd_program[] = {
        0xf2,0x0f,0x58,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, addsd_program, sizeof(addsd_program));
    cpu = fresh_cpu(&mmu);
    double one_half = 1.5, two_quarter = 2.25, expected_d = 3.75;
    memcpy(&cpu.xmm[0].u64[0], &one_half, sizeof(one_half));
    memcpy(&cpu.xmm[1].u64[0], &two_quarter, sizeof(two_quarter));
    cpu.xmm[0].u64[1] = 0x8877665544332211ULL;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    memcpy(&draw, &expected_d, sizeof(draw));
    assert(cpu.xmm[0].u64[0] == draw);
    assert(cpu.xmm[0].u64[1] == 0x8877665544332211ULL);

    // Memory source must read only the scalar lane: MULSS xmm2, [rdi].
    memset(memory, 0, sizeof(memory));
    const uint8_t mulss_mem_program[] = {
        0xf3,0x0f,0x59,0x17,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, mulss_mem_program, sizeof(mulss_mem_program));
    cpu = fresh_cpu(&mmu);
    const addr_t src = BASE + sizeof(memory) - 4;
    x86_64_set_reg(&cpu, X86_64_RDI, src);
    float four = 4.0f, two = 2.0f, eight = 8.0f;
    memcpy(&cpu.xmm[2].u32[0], &two, sizeof(two));
    memcpy(&memory[src - BASE], &four, sizeof(four));
    cpu.xmm[2].u32[1] = 0xa1b2c3d4U;
    cpu.xmm[2].u64[1] = 0x1020304050607080ULL;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    memcpy(&fraw, &eight, sizeof(fraw));
    assert(cpu.xmm[2].u32[0] == fraw);
    assert(cpu.xmm[2].u32[1] == 0xa1b2c3d4U);
    assert(cpu.xmm[2].u64[1] == 0x1020304050607080ULL);

    puts("DIRECT X86_64 SCALAR SSE ARITH: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_cvtsi2s();\n    test_write_exit();\n'''
main_replace = '''    test_cvtsi2s();\n    test_scalar_sse_arith();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 scalar SSE/SSE2 arithmetic and exact DIVSS regression")
