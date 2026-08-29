#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // CALL rel32.\n'''
insert = r'''        // TEST accumulator, immediate. A8 tests AL with imm8; A9 tests
        // AX/EAX/RAX with the operand-size immediate. These compact legacy
        // encodings still appear in modern glibc because x86 never forgets.
        if (op == 0xa8 || op == 0xa9) {
            unsigned test_bits;
            unsigned imm_bytes;
            uint64_t imm = 0;
            if (op == 0xa8) {
                test_bits = 8;
                imm_bytes = 1;
                uint8_t v;
                if (fetch_u8(cpu, ip + 1, &v) < 0) goto gpf;
                imm = v;
            } else if (operand16) {
                test_bits = 16;
                imm_bytes = 2;
                uint16_t v;
                if (fetch_u16(cpu, ip + 1, &v) < 0) goto gpf;
                imm = v;
            } else {
                test_bits = (rex & 0x8) ? 64 : 32;
                imm_bytes = 4;
                uint32_t v;
                if (fetch_u32(cpu, ip + 1, &v) < 0) goto gpf;
                imm = test_bits == 64 ? (uint64_t)(int64_t)(int32_t)v : v;
            }
            set_logic_flags(cpu, read_reg_bits(cpu, X86_64_RAX, test_bits) & imm, test_bits);
            cpu->pc = ip + 1 + imm_bytes;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("CALL anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with accumulator TEST")
