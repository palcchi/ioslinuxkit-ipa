#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // F3/F2 0F 10/11: MOVSS/MOVSD. Scalar stores must write only
            // 4 or 8 bytes. Treating these prefixes as packed MOVUPS/MOVUPD
            // corrupts adjacent stack slots and, in BDS, overwrites saved RBX.
            if ((rep_prefix == 0xf3 || rep_prefix == 0xf2) &&
                (op2 == 0x10 || op2 == 0x11)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                unsigned scalar_bytes = rep_prefix == 0xf3 ? 4 : 8;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;

                if (op2 == 0x10) {
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        if (scalar_bytes == 4)
                            cpu->xmm[xmm].u32[0] = cpu->xmm[rm.reg].u32[0];
                        else
                            cpu->xmm[xmm].u64[0] = cpu->xmm[rm.reg].u64[0];
                    } else if (scalar_bytes == 4) {
                        uint32_t value;
                        if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                        cpu->xmm[xmm].u128 = 0;
                        cpu->xmm[xmm].u32[0] = value;
                    } else {
                        uint64_t value;
                        if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                        cpu->xmm[xmm].u128 = 0;
                        cpu->xmm[xmm].u64[0] = value;
                    }
                } else {
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        if (scalar_bytes == 4)
                            cpu->xmm[rm.reg].u32[0] = cpu->xmm[xmm].u32[0];
                        else
                            cpu->xmm[rm.reg].u64[0] = cpu->xmm[xmm].u64[0];
                    } else if (scalar_bytes == 4) {
                        uint32_t value = cpu->xmm[xmm].u32[0];
                        if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                    } else {
                        uint64_t value = cpu->xmm[xmm].u64[0];
                        if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                    }
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // 0F 10/11 and 0F 28/29: MOVUPS/MOVAPS. The 66-prefixed
            // forms (MOVUPD/MOVAPD) have identical 128-bit copy semantics here.
            // F2/F3 scalar 10/11 forms are handled above.
            // Alignment faults are intentionally deferred during loader bring-up.
            if ((rep_prefix != 0xf2 && rep_prefix != 0xf3) &&
                (op2 == 0x10 || op2 == 0x11 || op2 == 0x28 || op2 == 0x29)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (op2 == 0x10) {
                    fprintf(stderr,
                            "[vmine-0f10-decoded] xmm=%u isreg=%d rmreg=%u addr=%llx next=%llx\n",
                            xmm, rm.is_reg ? 1 : 0, rm.reg,
                            (unsigned long long)rm.addr,
                            (unsigned long long)next);
                }
                if (xmm >= 16) goto undefined;
                bool load = (op2 == 0x10 || op2 == 0x28);
                if (load) {
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

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)

# Regression for the exact BDS corruption mechanism. MOVSS [rdi], xmm0 must
# update four bytes only and leave the following saved-register bytes intact.
test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_scalar_sse_moves(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    memset(memory, 0, sizeof(memory));
    const uint8_t movss_store[] = {
        0xf3,0x0f,0x11,0x07,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, movss_store, sizeof(movss_store));
    const addr_t dst = BASE + 0x300;
    memset(&memory[dst - BASE], 0x77, 16);
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RDI, dst);
    cpu.xmm[0].u32[0] = 0x0000007cU;
    cpu.xmm[0].u32[1] = 0xdeadbeefU;
    cpu.xmm[0].u64[1] = 0x1122334455667788ULL;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    uint32_t stored32 = 0;
    memcpy(&stored32, &memory[dst - BASE], sizeof(stored32));
    assert(stored32 == 0x0000007cU);
    for (unsigned i = 4; i < 16; i++)
        assert(memory[(dst - BASE) + i] == 0x77);

    memset(memory, 0, sizeof(memory));
    const uint8_t movsd_store[] = {
        0xf2,0x0f,0x11,0x07,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, movsd_store, sizeof(movsd_store));
    memset(&memory[dst - BASE], 0x55, 16);
    cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RDI, dst);
    cpu.xmm[0].u64[0] = 0x0102030405060708ULL;
    cpu.xmm[0].u64[1] = 0xaabbccddeeff0011ULL;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    uint64_t stored64 = 0;
    memcpy(&stored64, &memory[dst - BASE], sizeof(stored64));
    assert(stored64 == 0x0102030405060708ULL);
    for (unsigned i = 8; i < 16; i++)
        assert(memory[(dst - BASE) + i] == 0x55);

    puts("DIRECT X86_64 SCALAR SSE MOVES: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
main_replace = '''    test_scalar_sse_moves();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 interpreter with scalar and packed SSE moves")
