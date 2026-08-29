#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()

old_prefix = '''        bool rep_prefix = false;\n'''
new_prefix = '''        uint8_t rep_prefix = 0;\n'''
if old_prefix not in s:
    raise SystemExit("rep_prefix declaration anchor missing")
s = s.replace(old_prefix, new_prefix, 1)

old_parse = '''            if (op == 0xf3) { rep_prefix = true; ip++; continue; }\n            if (op == 0xf2) { rep_prefix = true; ip++; continue; }\n'''
new_parse = '''            if (op == 0xf3) { rep_prefix = 0xf3; ip++; continue; }\n            if (op == 0xf2) { rep_prefix = 0xf2; ip++; continue; }\n'''
if old_parse not in s:
    raise SystemExit("rep prefix parser anchor missing")
s = s.replace(old_parse, new_parse, 1)

anchor = '''            // SYSCALL.\n'''
insert = r'''            // F3 0F 2A /r: CVTSI2SS xmm, r/m32.
            // F3 REX.W 0F 2A /r: CVTSI2SS xmm, r/m64.
            // F2 0F 2A /r: CVTSI2SD xmm, r/m32.
            // F2 REX.W 0F 2A /r: CVTSI2SD xmm, r/m64.
            // Only the low scalar lane is replaced; upper XMM bits survive.
            if ((rep_prefix == 0xf3 || rep_prefix == 0xf2) && op2 == 0x2a) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                unsigned src_bits = (rex & 0x8) ? 64 : 32;
                uint64_t raw;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm_read(cpu, &rm, src_bits, &raw) < 0) goto gpf;

                if (rep_prefix == 0xf3) {
                    float out = src_bits == 64 ? (float)(int64_t)raw : (float)(int32_t)(uint32_t)raw;
                    uint32_t out_raw;
                    memcpy(&out_raw, &out, sizeof(out_raw));
                    cpu->xmm[xmm].u32[0] = out_raw;
                } else {
                    double out = src_bits == 64 ? (double)(int64_t)raw : (double)(int32_t)(uint32_t)raw;
                    uint64_t out_raw;
                    memcpy(&out_raw, &out, sizeof(out_raw));
                    cpu->xmm[xmm].u64[0] = out_raw;
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

# Inject an exact direct-interpreter regression into the existing smoke test so
# the same CI compile exercises F3/F2 identity plus 32/64-bit signed sources.
test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_cvtsi2s(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    uint32_t fraw;
    uint64_t draw;

    // Exact BDS frontier: F3 48 0F 2A C1 = CVTSI2SS xmm0, rcx (signed 64-bit).
    memset(memory, 0, sizeof(memory));
    const uint8_t ss64_program[] = {
        0xf3,0x48,0x0f,0x2a,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, ss64_program, sizeof(ss64_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u128 = (((__uint128_t)0x1122334455667788ULL) << 64) | 0x99aabbccddeeff00ULL;
    x86_64_set_reg(&cpu, X86_64_RCX, (uint64_t)(int64_t)-3);
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    float f = -3.0f;
    memcpy(&fraw, &f, sizeof(fraw));
    assert(cpu.xmm[0].u32[0] == fraw);
    assert(cpu.xmm[0].u32[1] == 0x99aabbccU);
    assert(cpu.xmm[0].u64[1] == 0x1122334455667788ULL);

    // F3 without REX.W consumes a signed 32-bit integer, ignoring high RCX.
    memset(memory, 0, sizeof(memory));
    const uint8_t ss32_program[] = {
        0xf3,0x0f,0x2a,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, ss32_program, sizeof(ss32_program));
    cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RCX, 0x12345678fffffffdULL);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(cpu.xmm[0].u32[0] == fraw);

    // F2 must remain distinguishable from F3: CVTSI2SD writes a double lane.
    memset(memory, 0, sizeof(memory));
    const uint8_t sd64_program[] = {
        0xf2,0x48,0x0f,0x2a,0xc1,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, sd64_program, sizeof(sd64_program));
    cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u64[1] = 0x8877665544332211ULL;
    x86_64_set_reg(&cpu, X86_64_RCX, (uint64_t)(int64_t)-3);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    double d = -3.0;
    memcpy(&draw, &d, sizeof(draw));
    assert(cpu.xmm[0].u64[0] == draw);
    assert(cpu.xmm[0].u64[1] == 0x8877665544332211ULL);

    puts("DIRECT X86_64 CVTSI2S: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
# Keep the test-call insertion composable with earlier bring-up patches such as
# F6 byte DIV, which also insert a regression immediately before write_exit.
main_anchor = '''    test_write_exit();\n'''
main_replace = '''    test_cvtsi2s();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 scalar integer-to-float conversions and exact regression")
