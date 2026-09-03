#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = """            // IMUL r, r/m.
"""
insert = r'''            // SHLD/SHRD r/m, r, imm8|CL. BDS uses SHLD r64,r64,CL
            // while initializing the published server build.
            if (op2 == 0xa4 || op2 == 0xa5 || op2 == 0xac || op2 == 0xad) {
                bool right = op2 == 0xac || op2 == 0xad;
                bool by_cl = op2 == 0xa5 || op2 == 0xad;
                unsigned imm_bytes = by_cl ? 0 : 1;
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, imm_bytes,
                              &rm, &reg, &next) < 0)
                    goto gpf;
                unsigned count;
                if (by_cl) {
                    count = (unsigned)read_reg_bits(cpu, X86_64_RCX, 8);
                } else {
                    uint8_t raw;
                    if (fetch_u8(cpu, next - 1, &raw) < 0) goto gpf;
                    count = raw;
                }
                count &= bits == 64 ? 63u : 31u;
                if (count != 0) {
                    uint64_t dst;
                    if (rm_read(cpu, &rm, bits, &dst) < 0) goto gpf;
                    uint64_t src = read_reg_bits(cpu, reg, bits);
                    uint64_t result;
                    if (right) {
                        cpu->cf = (dst >> (count - 1)) & 1;
                        result = (dst >> count) | (src << (bits - count));
                        if (count == 1)
                            cpu->vf = ((dst ^ result) & sign_bit(bits)) != 0;
                    } else {
                        cpu->cf = (dst >> (bits - count)) & 1;
                        result = (dst << count) | (src >> (bits - count));
                        if (count == 1)
                            cpu->vf = ((result & sign_bit(bits)) != 0) ^ cpu->cf;
                    }
                    result &= bits_mask(bits);
                    cpu->zf = result == 0;
                    cpu->nf = (result & sign_bit(bits)) != 0;
                    if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F double-shift anchor missing")
path.write_text(s.replace(anchor, insert + anchor, 1))
print("patched x86_64 SHLD/SHRD double shifts")
