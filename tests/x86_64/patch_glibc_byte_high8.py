from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()

old = '''#define INTERP_SLICE 100000

#define ARCH_SET_GS'''
new = '''#define INTERP_SLICE 100000
#define X86_64_HIGH8_MARK 0x100u

#define ARCH_SET_GS'''
if old not in s:
    raise SystemExit("constant anchor not found")
s = s.replace(old, new, 1)

old = '''static uint64_t read_reg_bits(struct cpu_state *cpu, unsigned reg, unsigned bits) {
    return x86_64_get_reg(cpu, reg) & bits_mask(bits);
}

static void write_reg_bits(struct cpu_state *cpu, unsigned reg, uint64_t value, unsigned bits) {
    if (bits == 64 || bits == 32) {
        // x86-64 32-bit register writes zero-extend into the full register.
        x86_64_set_reg(cpu, reg, value & bits_mask(bits));
        return;
    }
    uint64_t old = x86_64_get_reg(cpu, reg);
    uint64_t mask = bits_mask(bits);
    x86_64_set_reg(cpu, reg, (old & ~mask) | (value & mask));
}
'''
new = '''static uint64_t read_reg_bits(struct cpu_state *cpu, unsigned reg, unsigned bits) {
    // Without a REX prefix, byte-register encodings 4..7 mean AH/CH/DH/BH.
    // decode_rm tags only instructions whose operand encoding is actually byte
    // sized, so XMM4..XMM7 and ordinary wider GPR uses remain untouched.
    if (bits == 8 && (reg & X86_64_HIGH8_MARK)) {
        unsigned base = (reg & 7u) - 4u; // AH->RAX, CH->RCX, DH->RDX, BH->RBX
        return (x86_64_get_reg(cpu, base) >> 8) & 0xffu;
    }
    return x86_64_get_reg(cpu, reg) & bits_mask(bits);
}

static void write_reg_bits(struct cpu_state *cpu, unsigned reg, uint64_t value, unsigned bits) {
    if (bits == 8 && (reg & X86_64_HIGH8_MARK)) {
        unsigned base = (reg & 7u) - 4u;
        uint64_t old = x86_64_get_reg(cpu, base);
        x86_64_set_reg(cpu, base, (old & ~0xff00ULL) | ((value & 0xffULL) << 8));
        return;
    }
    if (bits == 64 || bits == 32) {
        // x86-64 32-bit register writes zero-extend into the full register.
        x86_64_set_reg(cpu, reg, value & bits_mask(bits));
        return;
    }
    uint64_t old = x86_64_get_reg(cpu, reg);
    uint64_t mask = bits_mask(bits);
    x86_64_set_reg(cpu, reg, (old & ~mask) | (value & mask));
}
'''
if old not in s:
    raise SystemExit("register bit helper block not found")
s = s.replace(old, new, 1)

old = '''    unsigned mod = modrm >> 6;
    unsigned raw_rm = modrm & 7;
    if (reg_field != NULL)
        *reg_field = ((modrm >> 3) & 7) | ((rex & 0x4) ? 8 : 0);

    addr_t p = modrm_addr + 1;
    if (mod == 3) {
        rm->is_reg = true;
        rm->reg = raw_rm | ((rex & 0x1) ? 8 : 0);
'''
new = '''    unsigned mod = modrm >> 6;
    unsigned raw_rm = modrm & 7;
    unsigned raw_reg = (modrm >> 3) & 7;

    // High-byte aliases exist only for 8-bit operand encodings. The earlier
    // bring-up version tagged every no-REX ModRM code 4..7, which accidentally
    // turned XMM4..XMM7 into 0x104..0x107. Determine byte semantics from the
    // opcode immediately preceding this ModRM (or the 0F opcode pair).
    uint8_t prev_op = 0, prev2_op = 0;
    bool byte_encoding = false;
    if (modrm_addr > 0 && fetch_u8(cpu, modrm_addr - 1, &prev_op) == 0) {
        switch (prev_op) {
            // r/m8,r8 and r8,r/m8 ALU families plus TEST/XCHG/MOV.
            case 0x00: case 0x02: case 0x08: case 0x0a:
            case 0x10: case 0x12: case 0x18: case 0x1a:
            case 0x20: case 0x22: case 0x28: case 0x2a:
            case 0x30: case 0x32: case 0x38: case 0x3a:
            case 0x84: case 0x86: case 0x88: case 0x8a:
            // Immediate/group and shift byte forms.
            case 0x80: case 0xc0: case 0xc6: case 0xd0: case 0xd2:
            case 0xf6: case 0xfe:
                byte_encoding = true;
                break;
            default:
                break;
        }
        if (modrm_addr > 1 && fetch_u8(cpu, modrm_addr - 2, &prev2_op) == 0 && prev2_op == 0x0f) {
            // SETcc r/m8 and MOVZX/MOVSX from r/m8.
            if ((prev_op >= 0x90 && prev_op <= 0x9f) || prev_op == 0xb6 || prev_op == 0xbe)
                byte_encoding = true;
        }
    }

    if (reg_field != NULL) {
        *reg_field = raw_reg | ((rex & 0x4) ? 8 : 0);
        if (byte_encoding && rex == 0 && raw_reg >= 4)
            *reg_field |= X86_64_HIGH8_MARK;
    }

    addr_t p = modrm_addr + 1;
    if (mod == 3) {
        rm->is_reg = true;
        rm->reg = raw_rm | ((rex & 0x1) ? 8 : 0);
        if (byte_encoding && rex == 0 && raw_rm >= 4)
            rm->reg |= X86_64_HIGH8_MARK;
'''
if old not in s:
    raise SystemExit("ModRM register decode anchor not found")
s = s.replace(old, new, 1)

p.write_text(s)
print("patched x86_64 legacy AH/CH/DH/BH decoding only for byte opcodes")
