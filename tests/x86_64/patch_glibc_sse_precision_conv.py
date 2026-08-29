#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // F3 0F 5A: CVTSS2SD, F2 0F 5A: CVTSD2SS.
            if ((rep_prefix == 0xf3 || rep_prefix == 0xf2) && op2 == 0x5a) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rep_prefix == 0xf3) {
                    uint32_t raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        raw = cpu->xmm[rm.reg].u32[0];
                    } else if (guest_read(cpu, rm.addr, &raw, sizeof(raw)) < 0) goto gpf;
                    float src;
                    double out;
                    memcpy(&src, &raw, sizeof(src));
                    out = (double)src;
                    memcpy(&cpu->xmm[xmm].u64[0], &out, sizeof(out));
                } else {
                    uint64_t raw;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        raw = cpu->xmm[rm.reg].u64[0];
                    } else if (guest_read(cpu, rm.addr, &raw, sizeof(raw)) < 0) goto gpf;
                    double src;
                    float out;
                    memcpy(&src, &raw, sizeof(src));
                    out = (float)src;
                    memcpy(&cpu->xmm[xmm].u32[0], &out, sizeof(out));
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
test_insert = r'''static void test_scalar_precision_conv(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0xf3,0x0f,0x5a,0xc8,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    float src = 3.25f;
    double expected = 3.25;
    memcpy(&cpu.xmm[0].u32[0], &src, sizeof(src));
    cpu.xmm[1].u64[1] = 0x1122334455667788ULL;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    uint64_t raw;
    memcpy(&raw, &expected, sizeof(raw));
    assert(cpu.xmm[1].u64[0] == raw);
    assert(cpu.xmm[1].u64[1] == 0x1122334455667788ULL);
    puts("DIRECT X86_64 SCALAR PRECISION CONV: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
main_replace = '''    test_scalar_precision_conv();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)
print("patched x86_64 scalar SSE precision conversions")
