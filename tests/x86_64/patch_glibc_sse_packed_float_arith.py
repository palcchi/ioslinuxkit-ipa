#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // Legacy packed SSE/SSE2 floating-point arithmetic.
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
test_insert = r'''static void test_packed_sse_float_arith(void) {
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
main_replace = '''    test_packed_sse_float_arith();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 packed SSE/SSE2 floating-point arithmetic")
