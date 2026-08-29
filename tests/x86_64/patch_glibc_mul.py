#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
insert = r'''        // F7 /4,/5: one-operand MUL/IMUL. The x86_64 dynamic loader uses
        // MUL while hashing and sizing internal tables, long before main().
        if (op == 0xf7) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned group_raw = (modrm >> 3) & 7;
            if (group_raw == 4 || group_raw == 5) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                unsigned mul_bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);
                uint64_t src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &group, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, mul_bits, &src) < 0) goto gpf;
                uint64_t acc = read_reg_bits(cpu, X86_64_RAX, mul_bits);
                uint64_t low, high;
                bool overflow;

                if ((group & 7) == 4) {
                    __uint128_t product = (__uint128_t)(acc & bits_mask(mul_bits)) *
                                          (__uint128_t)(src & bits_mask(mul_bits));
                    low = (uint64_t)(product & bits_mask(mul_bits));
                    high = (uint64_t)((product >> mul_bits) & bits_mask(mul_bits));
                    overflow = high != 0;
                } else {
                    __int128 a, b;
                    if (mul_bits == 64) {
                        a = (int64_t)acc;
                        b = (int64_t)src;
                    } else if (mul_bits == 32) {
                        a = (int32_t)acc;
                        b = (int32_t)src;
                    } else {
                        a = (int16_t)acc;
                        b = (int16_t)src;
                    }
                    __int128 product = a * b;
                    __uint128_t raw = (__uint128_t)product;
                    low = (uint64_t)(raw & bits_mask(mul_bits));
                    high = (uint64_t)((raw >> mul_bits) & bits_mask(mul_bits));
                    __int128 min = -((__int128)1 << (mul_bits - 1));
                    __int128 max = (((__int128)1 << (mul_bits - 1)) - 1);
                    overflow = product < min || product > max;
                }

                write_reg_bits(cpu, X86_64_RAX, low, mul_bits);
                write_reg_bits(cpu, X86_64_RDX, high, mul_bits);
                cpu->cf = overflow;
                cpu->vf = overflow;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
        }

'''
if anchor not in s:
    raise SystemExit("F7 anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with one-operand MUL/IMUL")
