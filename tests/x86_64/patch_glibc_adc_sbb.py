#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

helper_anchor = '''static uint64_t read_reg_bits(struct cpu_state *cpu, unsigned reg, unsigned bits) {\n'''
helpers = r'''static uint64_t set_adc_flags(struct cpu_state *cpu, uint64_t a, uint64_t b,
                              unsigned carry, unsigned bits) {
    uint64_t mask = bits_mask(bits);
    uint64_t aa = a & mask;
    uint64_t bb = b & mask;
    __uint128_t wide = (__uint128_t)aa + (__uint128_t)bb + (carry ? 1 : 0);
    uint64_t result = (uint64_t)wide & mask;
    cpu->cf = bits == 64 ? (wide >> 64) != 0 : wide > mask;
    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
    return result;
}

static uint64_t set_sbb_flags(struct cpu_state *cpu, uint64_t a, uint64_t b,
                              unsigned borrow, unsigned bits) {
    uint64_t mask = bits_mask(bits);
    uint64_t aa = a & mask;
    uint64_t bb = b & mask;
    __uint128_t subtrahend = (__uint128_t)bb + (borrow ? 1 : 0);
    uint64_t result = (aa - bb - (borrow ? 1 : 0)) & mask;
    cpu->cf = (__uint128_t)aa < subtrahend;
    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
    return result;
}

'''
if helper_anchor not in s:
    raise SystemExit("register helper anchor missing")
s = s.replace(helper_anchor, helpers + helper_anchor, 1)

block_anchor = '''        // Binary register/memory ALU families.\n'''
block = r'''        // ADC/SBB register/memory families. These are split out from the
        // simple ALU block because they consume the incoming carry flag.
        if (op == 0x10 || op == 0x11 || op == 0x12 || op == 0x13 ||
            op == 0x18 || op == 0x19 || op == 0x1a || op == 0x1b) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            unsigned alu_bits = (op & 1) ? bits : 8;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            uint64_t rv, gv;
            if (rm_read(cpu, &rm, alu_bits, &rv) < 0) goto gpf;
            gv = read_reg_bits(cpu, reg, alu_bits);
            bool reverse = (op & 0x02) != 0;
            uint64_t a = reverse ? gv : rv;
            uint64_t b = reverse ? rv : gv;
            unsigned carry = cpu->cf ? 1 : 0;
            uint64_t result;
            if ((op & 0xf8) == 0x10)
                result = set_adc_flags(cpu, a, b, carry, alu_bits);
            else
                result = set_sbb_flags(cpu, a, b, carry, alu_bits);
            if (reverse)
                write_reg_bits(cpu, reg, result, alu_bits);
            else if (rm_write(cpu, &rm, alu_bits, result) < 0)
                goto gpf;
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if block_anchor not in s:
    raise SystemExit("binary ALU anchor missing")
s = s.replace(block_anchor, block + block_anchor, 1)

call_anchor = '''        // CALL rel32.\n'''
accum = r'''        // ADC/SBB accumulator-immediate legacy forms.
        if (op == 0x14 || op == 0x15 || op == 0x1c || op == 0x1d) {
            bool byte_form = (op == 0x14 || op == 0x1c);
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
            unsigned carry = cpu->cf ? 1 : 0;
            uint64_t result = (op == 0x1c || op == 0x1d)
                ? set_sbb_flags(cpu, old, imm, carry, alu_bits)
                : set_adc_flags(cpu, old, imm, carry, alu_bits);
            write_reg_bits(cpu, X86_64_RAX, result, alu_bits);
            cpu->pc = ip + 1 + imm_bytes;
            cpu->cycle++;
            continue;
        }

'''
if call_anchor not in s:
    raise SystemExit("CALL anchor missing")
s = s.replace(call_anchor, accum + call_anchor, 1)

group_anchor = '''                case 1: result = old | imm; set_logic_flags(cpu, result, alu_bits); break;\n                case 4: result = old & imm; set_logic_flags(cpu, result, alu_bits); break;\n'''
group_new = '''                case 1: result = old | imm; set_logic_flags(cpu, result, alu_bits); break;\n                case 2: { unsigned c = cpu->cf ? 1 : 0; result = set_adc_flags(cpu, old, imm, c, alu_bits); break; }\n                case 3: { unsigned c = cpu->cf ? 1 : 0; result = set_sbb_flags(cpu, old, imm, c, alu_bits); break; }\n                case 4: result = old & imm; set_logic_flags(cpu, result, alu_bits); break;\n'''
if group_anchor not in s:
    raise SystemExit("group-1 immediate anchor missing")
s = s.replace(group_anchor, group_new, 1)

path.write_text(s)
print("patched x86_64 interpreter with complete ADC/SBB carry arithmetic")
