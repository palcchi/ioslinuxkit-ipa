#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
insert = r'''        // F7 /6,/7: one-operand DIV/IDIV. The dividend lives in the
        // double-width RDX:RAX pair and the quotient/remainder return in
        // RAX/RDX. glibc reaches the unsigned 64-bit form while sizing loader
        // data structures after libc has been mapped.
        if (op == 0xf7) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned group_raw = (modrm >> 3) & 7;
            if (group_raw == 6 || group_raw == 7) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                unsigned div_bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);
                uint64_t src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &group, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, div_bits, &src) < 0) goto gpf;
                src &= bits_mask(div_bits);
                if (src == 0)
                    goto undefined; // #DE plumbing is not exposed by this bring-up core yet.

                uint64_t quotient = 0, remainder = 0;
                if ((group & 7) == 6) {
                    if (div_bits == 64) {
                        __uint128_t dividend = ((__uint128_t)x86_64_get_reg(cpu, X86_64_RDX) << 64) |
                                               (__uint128_t)x86_64_get_reg(cpu, X86_64_RAX);
                        __uint128_t q = dividend / (__uint128_t)src;
                        __uint128_t r = dividend % (__uint128_t)src;
                        if (q > UINT64_MAX) goto undefined;
                        quotient = (uint64_t)q;
                        remainder = (uint64_t)r;
                    } else if (div_bits == 32) {
                        uint64_t dividend = ((uint64_t)(uint32_t)x86_64_get_reg(cpu, X86_64_RDX) << 32) |
                                            (uint32_t)x86_64_get_reg(cpu, X86_64_RAX);
                        uint64_t q = dividend / (uint32_t)src;
                        uint64_t r = dividend % (uint32_t)src;
                        if (q > UINT32_MAX) goto undefined;
                        quotient = (uint32_t)q;
                        remainder = (uint32_t)r;
                    } else {
                        uint32_t dividend = ((uint32_t)(uint16_t)x86_64_get_reg(cpu, X86_64_RDX) << 16) |
                                            (uint16_t)x86_64_get_reg(cpu, X86_64_RAX);
                        uint32_t q = dividend / (uint16_t)src;
                        uint32_t r = dividend % (uint16_t)src;
                        if (q > UINT16_MAX) goto undefined;
                        quotient = (uint16_t)q;
                        remainder = (uint16_t)r;
                    }
                } else {
                    if (div_bits == 64) {
                        __uint128_t raw = ((__uint128_t)x86_64_get_reg(cpu, X86_64_RDX) << 64) |
                                          (__uint128_t)x86_64_get_reg(cpu, X86_64_RAX);
                        __int128 dividend = (__int128)raw;
                        int64_t divisor = (int64_t)src;
                        if (divisor == 0) goto undefined;
                        if (raw == ((__uint128_t)1 << 127) && divisor == -1) goto undefined;
                        __int128 q = dividend / (__int128)divisor;
                        __int128 r = dividend % (__int128)divisor;
                        if (q < INT64_MIN || q > INT64_MAX) goto undefined;
                        quotient = (uint64_t)(int64_t)q;
                        remainder = (uint64_t)(int64_t)r;
                    } else if (div_bits == 32) {
                        uint64_t raw = ((uint64_t)(uint32_t)x86_64_get_reg(cpu, X86_64_RDX) << 32) |
                                       (uint32_t)x86_64_get_reg(cpu, X86_64_RAX);
                        int64_t dividend = (int64_t)raw;
                        int32_t divisor = (int32_t)src;
                        if (divisor == 0) goto undefined;
                        int64_t q = dividend / divisor;
                        int64_t r = dividend % divisor;
                        if (q < INT32_MIN || q > INT32_MAX) goto undefined;
                        quotient = (uint32_t)(int32_t)q;
                        remainder = (uint32_t)(int32_t)r;
                    } else {
                        uint32_t raw = ((uint32_t)(uint16_t)x86_64_get_reg(cpu, X86_64_RDX) << 16) |
                                       (uint16_t)x86_64_get_reg(cpu, X86_64_RAX);
                        int32_t dividend = (int32_t)raw;
                        int16_t divisor = (int16_t)src;
                        if (divisor == 0) goto undefined;
                        int32_t q = dividend / divisor;
                        int32_t r = dividend % divisor;
                        if (q < INT16_MIN || q > INT16_MAX) goto undefined;
                        quotient = (uint16_t)(int16_t)q;
                        remainder = (uint16_t)(int16_t)r;
                    }
                }

                write_reg_bits(cpu, X86_64_RAX, quotient, div_bits);
                write_reg_bits(cpu, X86_64_RDX, remainder, div_bits);
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
print("patched x86_64 interpreter with DIV/IDIV")
