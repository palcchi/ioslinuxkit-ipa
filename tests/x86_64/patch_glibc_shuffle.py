#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F C6 /r ib: SHUFPS. 66 0F C6 /r ib: SHUFPD.
            // glibc uses these during early CPU-feature/vector setup.
            if (op2 == 0xc6 && !rep_prefix) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                uint8_t imm;
                if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                union x86_64_xmm old = cpu->xmm[xmm];
                union x86_64_xmm out = old;
                if (operand16) {
                    // SHUFPD: low qword selected from old dest, high qword
                    // selected from source. Only imm bits 0 and 1 matter.
                    out.u64[0] = old.u64[(imm >> 0) & 1];
                    out.u64[1] = src.u64[(imm >> 1) & 1];
                } else {
                    // SHUFPS: first two dwords come from old dest, final two
                    // from source, each selected by its 2-bit immediate field.
                    out.u32[0] = old.u32[(imm >> 0) & 3];
                    out.u32[1] = old.u32[(imm >> 2) & 3];
                    out.u32[2] = src.u32[(imm >> 4) & 3];
                    out.u32[3] = src.u32[(imm >> 6) & 3];
                }
                cpu->xmm[xmm] = out;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // Packed shuffle family selected by mandatory legacy prefix:
            //   66 0F 70 /r ib: PSHUFD
            //   F2 0F 70 /r ib: PSHUFLW
            //   F3 0F 70 /r ib: PSHUFHW
            // BDS 1.26.44.3 currently reaches the F2 form during startup.
            if (op2 == 0x70 &&
                (operand16 || rep_prefix == 0xf2 || rep_prefix == 0xf3)) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                uint8_t imm;
                if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                union x86_64_xmm out = src;

                if (rep_prefix == 0xf2) {
                    // PSHUFLW shuffles only source words 0..3. Words 4..7
                    // are copied unchanged from the source operand.
                    for (unsigned i = 0; i < 4; i++)
                        out.u16[i] = src.u16[(imm >> (i * 2)) & 3];
                } else if (rep_prefix == 0xf3) {
                    // PSHUFHW copies the low qword and shuffles source words
                    // 4..7 into destination words 4..7.
                    for (unsigned i = 0; i < 4; i++)
                        out.u16[4 + i] = src.u16[4 + ((imm >> (i * 2)) & 3)];
                } else {
                    // PSHUFD shuffles all four source dwords.
                    for (unsigned i = 0; i < 4; i++)
                        out.u32[i] = src.u32[(imm >> (i * 2)) & 3];
                }

                cpu->xmm[xmm] = out;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)

# Regression coverage for all three mandatory-prefix forms. The first case
# starts with the exact four-byte BDS frontier (F2 0F 70 C1).
test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_packed_shuffle_family(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    // BDS frontier: PSHUFLW xmm0, xmm1, 0x1b. Reverse the low four words
    // while copying the source high qword unchanged.
    memset(memory, 0, sizeof(memory));
    const uint8_t pshuflw_program[] = {
        0xf2,0x0f,0x70,0xc1,0x1b,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, pshuflw_program, sizeof(pshuflw_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    for (unsigned i = 0; i < 8; i++) cpu.xmm[1].u16[i] = (uint16_t)(0x100 + i);
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(cpu.xmm[0].u16[0] == 0x103 && cpu.xmm[0].u16[1] == 0x102);
    assert(cpu.xmm[0].u16[2] == 0x101 && cpu.xmm[0].u16[3] == 0x100);
    for (unsigned i = 4; i < 8; i++) assert(cpu.xmm[0].u16[i] == (uint16_t)(0x100 + i));

    // PSHUFHW xmm2, xmm3, 0x1b. Low qword is copied, high words reverse.
    memset(memory, 0, sizeof(memory));
    const uint8_t pshufhw_program[] = {
        0xf3,0x0f,0x70,0xd3,0x1b,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, pshufhw_program, sizeof(pshufhw_program));
    cpu = fresh_cpu(&mmu);
    for (unsigned i = 0; i < 8; i++) cpu.xmm[3].u16[i] = (uint16_t)(0x200 + i);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    for (unsigned i = 0; i < 4; i++) assert(cpu.xmm[2].u16[i] == (uint16_t)(0x200 + i));
    assert(cpu.xmm[2].u16[4] == 0x207 && cpu.xmm[2].u16[5] == 0x206);
    assert(cpu.xmm[2].u16[6] == 0x205 && cpu.xmm[2].u16[7] == 0x204);

    // PSHUFD xmm4, xmm5, 0x1b. Reverse all four dwords.
    memset(memory, 0, sizeof(memory));
    const uint8_t pshufd_program[] = {
        0x66,0x0f,0x70,0xe5,0x1b,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, pshufd_program, sizeof(pshufd_program));
    cpu = fresh_cpu(&mmu);
    for (unsigned i = 0; i < 4; i++) cpu.xmm[5].u32[i] = 0x300 + i;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(cpu.xmm[4].u32[0] == 0x303 && cpu.xmm[4].u32[1] == 0x302);
    assert(cpu.xmm[4].u32[2] == 0x301 && cpu.xmm[4].u32[3] == 0x300);

    puts("DIRECT X86_64 PACKED SHUFFLE FAMILY: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
call_anchor = '''    test_write_exit();\n'''
if call_anchor not in t:
    raise SystemExit("direct smoke call anchor missing")
t = t.replace(call_anchor, '''    test_packed_shuffle_family();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 interpreter with SHUFPS/SHUFPD and PSHUFD/PSHUFLW/PSHUFHW")
