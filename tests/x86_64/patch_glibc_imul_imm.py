#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
insert = r'''        // 69 /r id and 6B /r ib: signed IMUL r, r/m, immediate.
        // glibc uses the REX.W 69 form while formatting directory metadata.
        if (op == 0x69 || op == 0x6b) {
            struct rm_operand rm;
            unsigned dst_reg;
            addr_t next;
            unsigned mul_bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);
            uint64_t src_raw;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &dst_reg, &next) < 0) goto gpf;
            if (dst_reg >= 16) goto undefined;
            if (rm_read(cpu, &rm, mul_bits, &src_raw) < 0) goto gpf;

            int64_t imm;
            addr_t end;
            if (op == 0x6b) {
                uint8_t raw;
                if (fetch_u8(cpu, next, &raw) < 0) goto gpf;
                imm = (int8_t)raw;
                end = next + 1;
            } else if (mul_bits == 16) {
                uint16_t raw;
                if (fetch_u16(cpu, next, &raw) < 0) goto gpf;
                imm = (int16_t)raw;
                end = next + 2;
            } else {
                // In 64-bit operand size, opcode 69 still carries imm32 and
                // sign-extends it to 64 bits.
                uint32_t raw;
                if (fetch_u32(cpu, next, &raw) < 0) goto gpf;
                imm = (int32_t)raw;
                end = next + 4;
            }

            __int128 lhs;
            if (mul_bits == 64)
                lhs = (int64_t)src_raw;
            else if (mul_bits == 32)
                lhs = (int32_t)src_raw;
            else
                lhs = (int16_t)src_raw;

            __int128 product = lhs * (__int128)imm;
            __int128 min_value = -((__int128)1 << (mul_bits - 1));
            __int128 max_value = ((__int128)1 << (mul_bits - 1)) - 1;
            bool overflow = product < min_value || product > max_value;

            write_reg_bits(cpu, dst_reg, (uint64_t)product, mul_bits);
            cpu->cf = overflow;
            cpu->vf = overflow;
            cpu->pc = end;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("IMUL immediate anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with IMUL immediate forms")
