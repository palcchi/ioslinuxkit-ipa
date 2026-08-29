#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
insert = r'''        // Byte form of the F6 group: TEST, NOT, NEG, MUL, IMUL, DIV,
        // and IDIV. BDS reaches the REX.B byte DIV form (41 F6 F5) while
        // building startup tables.
        if (op == 0xf6) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned group_raw = (modrm >> 3) & 7;
            unsigned imm_bytes = group_raw == 0 ? 1 : 0;
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            uint64_t value;
            if (rm_read(cpu, &rm, 8, &value) < 0) goto gpf;
            value &= UINT8_MAX;
            switch (group & 7) {
                case 0: {
                    uint8_t imm;
                    if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                    set_logic_flags(cpu, value & imm, 8);
                    break;
                }
                case 2:
                    if (rm_write(cpu, &rm, 8, ~value) < 0) goto gpf;
                    break;
                case 3: {
                    uint64_t result = set_sub_flags(cpu, 0, value, 8);
                    if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
                    break;
                }
                case 4: { // MUL r/m8: AX = AL * r/m8
                    uint16_t result = (uint16_t)(uint8_t)x86_64_get_reg(cpu, X86_64_RAX) *
                                      (uint16_t)(uint8_t)value;
                    write_reg_bits(cpu, X86_64_RAX, result, 16);
                    cpu->cf = cpu->vf = (result & 0xff00U) != 0;
                    break;
                }
                case 5: { // IMUL r/m8: AX = signed AL * signed r/m8
                    int16_t result = (int16_t)(int8_t)x86_64_get_reg(cpu, X86_64_RAX) *
                                     (int16_t)(int8_t)value;
                    write_reg_bits(cpu, X86_64_RAX, (uint16_t)result, 16);
                    cpu->cf = cpu->vf = result < INT8_MIN || result > INT8_MAX;
                    break;
                }
                case 6: { // DIV r/m8: AL = AX/src, AH = AX%src
                    uint8_t divisor = (uint8_t)value;
                    if (divisor == 0) goto undefined;
                    uint16_t dividend = (uint16_t)x86_64_get_reg(cpu, X86_64_RAX);
                    uint16_t quotient = dividend / divisor;
                    uint16_t remainder = dividend % divisor;
                    if (quotient > UINT8_MAX) goto undefined;
                    uint16_t ax = (uint16_t)((uint8_t)quotient | ((uint16_t)(uint8_t)remainder << 8));
                    write_reg_bits(cpu, X86_64_RAX, ax, 16);
                    break;
                }
                case 7: { // IDIV r/m8: signed AX / signed r/m8
                    int8_t divisor = (int8_t)value;
                    if (divisor == 0) goto undefined;
                    int16_t dividend = (int16_t)(uint16_t)x86_64_get_reg(cpu, X86_64_RAX);
                    int16_t quotient = dividend / divisor;
                    int16_t remainder = dividend % divisor;
                    if (quotient < INT8_MIN || quotient > INT8_MAX) goto undefined;
                    uint16_t ax = (uint16_t)(uint8_t)(int8_t)quotient |
                                  ((uint16_t)(uint8_t)(int8_t)remainder << 8);
                    write_reg_bits(cpu, X86_64_RAX, ax, 16);
                    break;
                }
                default:
                    goto undefined;
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("F7 anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)

test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
test_anchor = '''static void test_write_exit(void) {\n'''
test_insert = r'''static void test_byte_division(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    // Exact BDS frontier: 41 F6 F5 = DIV r13b. 600 / 10 = 60 with
    // remainder 0, intentionally producing syscall number 60 in AX so the
    // next two bytes can be SYSCALL without another instruction obscuring it.
    memset(memory, 0, sizeof(memory));
    const uint8_t div8_program[] = {0x41,0xf6,0xf5,0x0f,0x05};
    memcpy(memory, div8_program, sizeof(div8_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RAX, 600);
    x86_64_set_reg(&cpu, X86_64_R13, 10);
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert((x86_64_get_reg(&cpu, X86_64_RAX) & 0xffffU) == 60);

    // Signed byte sibling: -600 / -10 = 60, remainder 0.
    memset(memory, 0, sizeof(memory));
    const uint8_t idiv8_program[] = {0x41,0xf6,0xfd,0x0f,0x05};
    memcpy(memory, idiv8_program, sizeof(idiv8_program));
    cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RAX, (uint16_t)(int16_t)-600);
    x86_64_set_reg(&cpu, X86_64_R13, (uint8_t)(int8_t)-10);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL && cpu.x86_last_syscall == 60);
    assert((x86_64_get_reg(&cpu, X86_64_RAX) & 0xffffU) == 60);

    puts("DIRECT X86_64 BYTE DIV/IDIV: PASS");
}

'''
if test_anchor not in t:
    raise SystemExit("direct smoke function anchor missing")
t = t.replace(test_anchor, test_insert + test_anchor, 1)
call_anchor = '''    test_write_exit();\n'''
if call_anchor not in t:
    raise SystemExit("direct smoke call anchor missing")
t = t.replace(call_anchor, '''    test_byte_division();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 interpreter with complete F6 byte arithmetic group")
