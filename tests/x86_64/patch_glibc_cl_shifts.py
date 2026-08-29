#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // Shift group C1/D1: SHL/SHR/SAR with immediate or count=1.\n'''
insert = r'''        // D3 /0,/1,/4,/5,/7: scalar rotate/shift by CL. glibc's
        // baseline routines use the register-count form in addition to C1/D1.
        if (op == 0xd3) {
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &group, &next) < 0) goto gpf;
            unsigned raw_group = group & 7;
            if (raw_group != 0 && raw_group != 1 && raw_group != 4 &&
                raw_group != 5 && raw_group != 7)
                goto undefined;
            unsigned count = (unsigned)(read_reg_bits(cpu, X86_64_RCX, 8) &
                                        (bits == 64 ? 63u : 31u));
            if (raw_group == 0 || raw_group == 1)
                count %= bits;
            if (count != 0) {
                uint64_t value;
                if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
                value &= bits_mask(bits);
                uint64_t result = value;
                if (raw_group == 0) {
                    result = ((value << count) | (value >> (bits - count))) & bits_mask(bits);
                    cpu->cf = result & 1;
                    if (count == 1)
                        cpu->vf = ((result & sign_bit(bits)) != 0) ^ cpu->cf;
                } else if (raw_group == 1) {
                    result = ((value >> count) | (value << (bits - count))) & bits_mask(bits);
                    cpu->cf = (result & sign_bit(bits)) != 0;
                    if (count == 1) {
                        bool msb = (result & sign_bit(bits)) != 0;
                        bool next_msb = (result & (sign_bit(bits) >> 1)) != 0;
                        cpu->vf = msb ^ next_msb;
                    }
                } else if (raw_group == 4) {
                    if (count <= bits)
                        cpu->cf = (value >> (bits - count)) & 1;
                    result = count < bits ? (value << count) & bits_mask(bits) : 0;
                    if (count == 1)
                        cpu->vf = ((result & sign_bit(bits)) != 0) ^ cpu->cf;
                    cpu->zf = result == 0;
                    cpu->nf = (result & sign_bit(bits)) != 0;
                } else if (raw_group == 5) {
                    if (count <= bits)
                        cpu->cf = (value >> (count - 1)) & 1;
                    result = count < bits ? value >> count : 0;
                    if (count == 1)
                        cpu->vf = (value & sign_bit(bits)) != 0;
                    cpu->zf = result == 0;
                    cpu->nf = (result & sign_bit(bits)) != 0;
                } else {
                    if (count <= bits)
                        cpu->cf = (value >> (count - 1)) & 1;
                    if (bits == 64) {
                        result = count < 64 ? (uint64_t)((int64_t)value >> count)
                                            : ((int64_t)value < 0 ? UINT64_MAX : 0);
                    } else if (bits == 32) {
                        result = count < 32 ? (uint32_t)((int32_t)(uint32_t)value >> count)
                                            : ((int32_t)(uint32_t)value < 0 ? UINT32_MAX : 0);
                    } else {
                        result = count < 16 ? (uint16_t)((int16_t)(uint16_t)value >> count)
                                            : ((int16_t)(uint16_t)value < 0 ? UINT16_MAX : 0);
                    }
                    if (count == 1)
                        cpu->vf = 0;
                    cpu->zf = (result & bits_mask(bits)) == 0;
                    cpu->nf = (result & sign_bit(bits)) != 0;
                }
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("shift-group anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with scalar CL shifts")
