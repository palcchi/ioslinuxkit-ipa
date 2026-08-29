#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // F3 0F 2C /r: CVTTSS2SI r32/64, xmm/m32.
            // F2 0F 2C /r: CVTTSD2SI r32/64, xmm/m64.
            // Conversion truncates toward zero. Invalid/overflow produces the
            // architectural integer-indefinite value; FP exceptions are not
            // modelled yet during bring-up.
            if ((rep_prefix == 0xf3 || rep_prefix == 0xf2) && op2 == 0x2c) {
                struct rm_operand rm;
                unsigned dst;
                addr_t next;
                bool wide = (rex & 0x8) != 0;
                double value;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &dst, &next) < 0) goto gpf;
                if (dst >= 16) goto undefined;

                if (rep_prefix == 0xf3) {
                    uint32_t raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        raw = cpu->xmm[rm.reg].u32[0];
                    } else if (guest_read(cpu, rm.addr, &raw, sizeof(raw)) < 0) {
                        goto gpf;
                    }
                    float f;
                    memcpy(&f, &raw, sizeof(f));
                    value = (double)f;
                } else {
                    uint64_t raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        raw = cpu->xmm[rm.reg].u64[0];
                    } else if (guest_read(cpu, rm.addr, &raw, sizeof(raw)) < 0) {
                        goto gpf;
                    }
                    memcpy(&value, &raw, sizeof(value));
                }

                if (wide) {
                    uint64_t out;
                    if (!(value == value) ||
                        value < -9223372036854775808.0 ||
                        value >= 9223372036854775808.0) {
                        out = 0x8000000000000000ULL;
                    } else {
                        out = (uint64_t)(int64_t)value;
                    }
                    write_reg_bits(cpu, dst, out, 64);
                } else {
                    uint32_t out;
                    if (!(value == value) ||
                        value < -2147483648.0 ||
                        value >= 2147483648.0) {
                        out = 0x80000000U;
                    } else {
                        out = (uint32_t)(int32_t)value;
                    }
                    write_reg_bits(cpu, dst, out, 32);
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
test_insert = r'''static void test_cvtt_s2si(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    // Exact BDS frontier: F3 48 0F 2C C0 = CVTTSS2SI rax, xmm0.
    memset(memory, 0, sizeof(memory));
    const uint8_t ss64_program[] = {
        0xf3,0x48,0x0f,0x2c,0xc0,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, ss64_program, sizeof(ss64_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    float f = -3.75f;
    memcpy(&cpu.xmm[0].u32[0], &f, sizeof(f));
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    // RAX was overwritten with syscall 60 after conversion, so use RCX below
    // for an observable result in the same instruction family.

    memset(memory, 0, sizeof(memory));
    const uint8_t ss64_rcx_program[] = {
        0xf3,0x48,0x0f,0x2c,0xc8,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, ss64_rcx_program, sizeof(ss64_rcx_program));
    cpu = fresh_cpu(&mmu);
    memcpy(&cpu.xmm[0].u32[0], &f, sizeof(f));
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RCX) == (uint64_t)(int64_t)-3);

    // F2 32-bit destination must zero-extend EDX and use the XMM source.
    memset(memory, 0, sizeof(memory));
    const uint8_t sd32_program[] = {
        0xf2,0x0f,0x2c,0xd1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, sd32_program, sizeof(sd32_program));
    cpu = fresh_cpu(&mmu);
    double d = 42.9;
    memcpy(&cpu.xmm[1].u64[0], &d, sizeof(d));
    x86_64_set_reg(&cpu, X86_64_RDX, 0xffffffffffffffffULL);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RDX) == 42);

    // Memory source at the final four bytes of the test mapping proves the
    // scalar load does not over-read a whole XMM register.
    memset(memory, 0, sizeof(memory));
    const uint8_t mem_program[] = {
        0xf3,0x48,0x0f,0x2c,0x0f,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, mem_program, sizeof(mem_program));
    cpu = fresh_cpu(&mmu);
    const addr_t src = BASE + sizeof(memory) - 4;
    x86_64_set_reg(&cpu, X86_64_RDI, src);
    f = 7.99f;
    memcpy(&memory[src - BASE], &f, sizeof(f));
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RCX) == 7);

    // NaN yields the architectural integer-indefinite value.
    memset(memory, 0, sizeof(memory));
    memcpy(memory, ss64_rcx_program, sizeof(ss64_rcx_program));
    cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u32[0] = 0x7fc00000U;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RCX) == 0x8000000000000000ULL);

    puts("DIRECT X86_64 CVTTS2SI: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_scalar_sse_arith();\n    test_write_exit();\n'''
main_replace = '''    test_scalar_sse_arith();\n    test_cvtt_s2si();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 CVTTSS2SI/CVTTSD2SI and exact BDS regression")
