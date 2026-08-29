#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST accumulator, immediate. A8 tests AL with imm8; A9 tests\n'''
insert = r'''        // Legacy accumulator-immediate ALU encodings. Modern glibc still
        // emits the compact AL/EAX/RAX forms because x86 carries its ancestry
        // around like geological strata.
        if (op == 0x04 || op == 0x05 || // ADD AL/AX/EAX/RAX, imm
            op == 0x0c || op == 0x0d || // OR
            op == 0x24 || op == 0x25 || // AND
            op == 0x2c || op == 0x2d || // SUB
            op == 0x34 || op == 0x35 || // XOR
            op == 0x3c || op == 0x3d) { // CMP
            bool byte_form = (op & 1) == 0;
            unsigned alu_bits;
            unsigned imm_bytes;
            uint64_t imm;
            if (byte_form) {
                alu_bits = 8;
                imm_bytes = 1;
                uint8_t v;
                if (fetch_u8(cpu, ip + 1, &v) < 0) goto gpf;
                imm = v;
            } else if (operand16) {
                alu_bits = 16;
                imm_bytes = 2;
                uint16_t v;
                if (fetch_u16(cpu, ip + 1, &v) < 0) goto gpf;
                imm = v;
            } else {
                alu_bits = (rex & 0x8) ? 64 : 32;
                imm_bytes = 4;
                uint32_t v;
                if (fetch_u32(cpu, ip + 1, &v) < 0) goto gpf;
                imm = alu_bits == 64 ? (uint64_t)(int64_t)(int32_t)v : v;
            }

            uint64_t old = read_reg_bits(cpu, X86_64_RAX, alu_bits);
            uint64_t result = old;
            unsigned family = op & 0xf8;
            bool store = true;
            switch (family) {
                case 0x00: result = set_add_flags(cpu, old, imm, alu_bits); break;
                case 0x08: result = old | imm; set_logic_flags(cpu, result, alu_bits); break;
                case 0x20: result = old & imm; set_logic_flags(cpu, result, alu_bits); break;
                case 0x28: result = set_sub_flags(cpu, old, imm, alu_bits); break;
                case 0x30: result = old ^ imm; set_logic_flags(cpu, result, alu_bits); break;
                case 0x38: (void)set_sub_flags(cpu, old, imm, alu_bits); store = false; break;
                default: goto undefined;
            }
            if (store)
                write_reg_bits(cpu, X86_64_RAX, result, alu_bits);
            cpu->pc = ip + 1 + imm_bytes;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("accumulator TEST anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with accumulator immediate ALU")
