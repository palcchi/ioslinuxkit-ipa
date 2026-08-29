#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // Shift group C1/D1: SHL/SHR/SAR with immediate or count=1.\n'''
insert = r'''        // Byte shift group C0/D0/D2: ROL/ROR/SHL/SHR/SAR r/m8.
        // glibc uses compact byte shifts while decoding ELF and feature flags.
        if (op == 0xc0 || op == 0xd0 || op == 0xd2) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned raw_group = (modrm >> 3) & 7;
            if (raw_group == 0 || raw_group == 1 || raw_group == 4 ||
                raw_group == 5 || raw_group == 7) {
                unsigned imm_bytes = op == 0xc0 ? 1 : 0;
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
                uint8_t raw_count = 1;
                if (op == 0xc0) {
                    if (fetch_u8(cpu, next - 1, &raw_count) < 0) goto gpf;
                } else if (op == 0xd2) {
                    raw_count = (uint8_t)read_reg_bits(cpu, X86_64_RCX, 8);
                }
                unsigned count = raw_count & 31u;
                if (raw_group == 0 || raw_group == 1)
                    count %= 8;
                if (count != 0) {
                    uint64_t value64;
                    if (rm_read(cpu, &rm, 8, &value64) < 0) goto gpf;
                    uint8_t value = (uint8_t)value64;
                    uint8_t result = value;
                    if ((group & 7) == 0) {
                        result = (uint8_t)((value << count) | (value >> (8 - count)));
                        cpu->cf = result & 1;
                        if (count == 1)
                            cpu->vf = ((result & 0x80) != 0) ^ cpu->cf;
                    } else if ((group & 7) == 1) {
                        result = (uint8_t)((value >> count) | (value << (8 - count)));
                        cpu->cf = (result & 0x80) != 0;
                        if (count == 1)
                            cpu->vf = ((result >> 7) ^ (result >> 6)) & 1;
                    } else if ((group & 7) == 4) {
                        if (count <= 8)
                            cpu->cf = (value >> (8 - count)) & 1;
                        result = count < 8 ? (uint8_t)(value << count) : 0;
                        if (count == 1)
                            cpu->vf = ((result & 0x80) != 0) ^ cpu->cf;
                        cpu->zf = result == 0;
                        cpu->nf = (result & 0x80) != 0;
                    } else if ((group & 7) == 5) {
                        if (count <= 8)
                            cpu->cf = (value >> (count - 1)) & 1;
                        result = count < 8 ? (uint8_t)(value >> count) : 0;
                        if (count == 1)
                            cpu->vf = (value & 0x80) != 0;
                        cpu->zf = result == 0;
                        cpu->nf = (result & 0x80) != 0;
                    } else {
                        if (count <= 8)
                            cpu->cf = (value >> (count - 1)) & 1;
                        int8_t signed_value = (int8_t)value;
                        result = count < 8
                            ? (uint8_t)(signed_value >> count)
                            : (signed_value < 0 ? UINT8_MAX : 0);
                        if (count == 1)
                            cpu->vf = 0;
                        cpu->zf = result == 0;
                        cpu->nf = (result & 0x80) != 0;
                    }
                    if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
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
print("patched x86_64 interpreter with byte shift group")
