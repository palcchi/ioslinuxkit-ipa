#!/usr/bin/env python3
from pathlib import Path

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
anchor = '''        // Binary register/memory ALU families.\n'''
insert = r'''        // FE /0 and /1: INC/DEC r/m8. These update arithmetic flags while
        // preserving CF, unlike ADD/SUB. BDS uses FE C9 (DEC CL) in a hot path.
        if (op == 0xfe) {
            struct rm_operand rm;
            unsigned subop;
            addr_t next;
            uint64_t value;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &subop, &next) < 0) goto gpf;
            subop &= 7;
            if (subop != 0 && subop != 1) goto undefined;
            if (rm_read(cpu, &rm, 8, &value) < 0) goto gpf;
            bool saved_cf = cpu->cf;
            uint64_t result;
            if (subop == 0)
                result = set_add_flags(cpu, value, 1, 8);
            else
                result = set_sub_flags(cpu, value, 1, 8);
            cpu->cf = saved_cf;
            if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("binary ALU anchor missing")
s = s.replace(anchor, insert + anchor, 1)
interp.write_text(s)

test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_byte_incdec(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0xfe,0xc9,                   // DEC CL
        0xfe,0xc1,                   // INC CL
        0x48,0x89,0xcf,             // MOV RDI, RCX
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RCX, 0x1122334455667788ULL);
    cpu.cf = true;
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RDI) == 0x1122334455667788ULL);
    assert(cpu.cf == true);
    puts("DIRECT X86_64 BYTE INCDEC: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
main_replace = '''    test_byte_incdec();\n    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("direct smoke main anchor missing")
t = t.replace(main_anchor, main_replace, 1)
test.write_text(t)

print("patched x86_64 FE byte INC/DEC")
