#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // Binary register/memory ALU families.\n'''
insert = r'''        // Byte register/memory ALU forms. The scalar core already handles
        // the word/dword/qword 01/03-style encodings; glibc also uses the
        // compact 00/02 ... 38/3A forms for feature-byte comparisons.
        if (op == 0x00 || op == 0x02 || op == 0x08 || op == 0x0a ||
            op == 0x20 || op == 0x22 || op == 0x28 || op == 0x2a ||
            op == 0x30 || op == 0x32 || op == 0x38 || op == 0x3a) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            uint64_t rv, gv;
            if (rm_read(cpu, &rm, 8, &rv) < 0) goto gpf;
            gv = read_reg_bits(cpu, reg, 8);
            bool reverse = (op & 0x02) != 0;
            uint64_t a = reverse ? gv : rv;
            uint64_t b = reverse ? rv : gv;
            uint64_t result = 0;
            unsigned family = op & 0xf8;
            if (family == 0x00) {
                result = set_add_flags(cpu, a, b, 8);
                if (reverse) write_reg_bits(cpu, reg, result, 8);
                else if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            } else if (family == 0x08) {
                result = a | b; set_logic_flags(cpu, result, 8);
                if (reverse) write_reg_bits(cpu, reg, result, 8);
                else if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            } else if (family == 0x20) {
                result = a & b; set_logic_flags(cpu, result, 8);
                if (reverse) write_reg_bits(cpu, reg, result, 8);
                else if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            } else if (family == 0x28) {
                result = set_sub_flags(cpu, a, b, 8);
                if (reverse) write_reg_bits(cpu, reg, result, 8);
                else if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            } else if (family == 0x30) {
                result = a ^ b; set_logic_flags(cpu, result, 8);
                if (reverse) write_reg_bits(cpu, reg, result, 8);
                else if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
            } else if (family == 0x38) {
                (void)set_sub_flags(cpu, a, b, 8);
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("binary ALU anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with byte register ALU forms")
