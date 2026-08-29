#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // Shift group C1/D1: SHL/SHR/SAR with immediate or count=1.\n'''
insert = r'''        // C1/D1 /0,/1: ROL/ROR. glibc uses rotates in its hashing code.
        if (op == 0xc1 || op == 0xd1) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned raw_group = (modrm >> 3) & 7;
            if (raw_group == 0 || raw_group == 1) {
                unsigned imm_bytes = op == 0xc1 ? 1 : 0;
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
                uint8_t raw_count = 1;
                if (op == 0xc1 && fetch_u8(cpu, next - 1, &raw_count) < 0) goto gpf;
                unsigned count = raw_count & (bits == 64 ? 63u : 31u);
                count %= bits;
                if (count != 0) {
                    uint64_t value;
                    if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
                    uint64_t mask = bits_mask(bits);
                    value &= mask;
                    uint64_t result;
                    if ((group & 7) == 0) {
                        result = ((value << count) | (value >> (bits - count))) & mask;
                        cpu->cf = result & 1;
                        if (count == 1)
                            cpu->vf = ((result & sign_bit(bits)) != 0) ^ cpu->cf;
                    } else {
                        result = ((value >> count) | (value << (bits - count))) & mask;
                        cpu->cf = (result & sign_bit(bits)) != 0;
                        if (count == 1) {
                            bool msb = (result & sign_bit(bits)) != 0;
                            bool next_msb = (result & (sign_bit(bits) >> 1)) != 0;
                            cpu->vf = msb ^ next_msb;
                        }
                    }
                    if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
        }

'''
if anchor not in s:
    raise SystemExit("shift-group anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with ROL/ROR")
