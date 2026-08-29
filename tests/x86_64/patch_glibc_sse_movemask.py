#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 50 /r: MOVMSKPS r32, xmm. 66 0F 50 /r: MOVMSKPD.
            // The source is always an XMM register. The destination is a
            // 32-bit GPR write, so x86-64 zero-extends it into the full GPR.
            if (op2 == 0x50 && !rep_prefix) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (!rm.is_reg || rm.reg >= 16 || reg >= 16) goto undefined;

                uint32_t mask = 0;
                if (operand16) {
                    // MOVMSKPD: sign bit from each packed double -> bits 0..1.
                    for (unsigned i = 0; i < 2; i++)
                        mask |= (uint32_t)((cpu->xmm[rm.reg].u64[i] >> 63) & 1) << i;
                } else {
                    // MOVMSKPS: sign bit from each packed float -> bits 0..3.
                    for (unsigned i = 0; i < 4; i++)
                        mask |= (uint32_t)((cpu->xmm[rm.reg].u32[i] >> 31) & 1) << i;
                }
                write_reg_bits(cpu, reg, mask, 32);
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
test_insert = r'''static void test_sse_movemask(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    // Exact BDS frontier: 66 0F 50 C0 = MOVMSKPD eax, xmm0.
    memset(memory, 0, sizeof(memory));
    const uint8_t movmskpd_program[] = {
        0x66,0x0f,0x50,0xc0,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, movmskpd_program, sizeof(movmskpd_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u64[0] = 0x0123456789abcdefULL;
    cpu.xmm[0].u64[1] = 0xfedcba9876543210ULL;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    // The test program overwrites RAX with syscall 60 after MOVMSKPD, so use
    // R11 as destination in a second exact-semantics sample below.

    memset(memory, 0, sizeof(memory));
    const uint8_t movmskpd_r11_program[] = {
        0x66,0x44,0x0f,0x50,0xd8,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, movmskpd_r11_program, sizeof(movmskpd_r11_program));
    cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u64[0] = 0x0123456789abcdefULL;
    cpu.xmm[0].u64[1] = 0xfedcba9876543210ULL;
    x86_64_set_reg(&cpu, X86_64_R11, UINT64_MAX);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_R11) == 2);

    // MOVMSKPS r10d, xmm1: negative lanes 1 and 3 -> binary 1010.
    memset(memory, 0, sizeof(memory));
    const uint8_t movmskps_program[] = {
        0x44,0x0f,0x50,0xd1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, movmskps_program, sizeof(movmskps_program));
    cpu = fresh_cpu(&mmu);
    cpu.xmm[1].u32[0] = 0x00000000U;
    cpu.xmm[1].u32[1] = 0x80000000U;
    cpu.xmm[1].u32[2] = 0x7fffffffU;
    cpu.xmm[1].u32[3] = 0xffffffffU;
    x86_64_set_reg(&cpu, X86_64_R10, UINT64_MAX);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_R10) == 0x0a);

    puts("DIRECT X86_64 SSE MOVEMASK: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
call_anchor = '''    test_write_exit();\n'''
if call_anchor not in t:
    raise SystemExit("direct smoke call anchor missing")
t = t.replace(call_anchor, '''    test_sse_movemask();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 interpreter with MOVMSKPS/MOVMSKPD")
