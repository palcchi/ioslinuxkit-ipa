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
    // Without a REX prefix, ModRM byte-register encodings 4..7 mean
    // AH/CH/DH/BH, not SPL/BPL/SIL/DIL. The decoder tags those encodings so
    // the ordinary word/dword/qword register numbering can remain unchanged.
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
    if (reg_field != NULL) {
        *reg_field = raw_reg | ((rex & 0x4) ? 8 : 0);
        if (rex == 0 && raw_reg >= 4)
            *reg_field |= X86_64_HIGH8_MARK;
    }

    addr_t p = modrm_addr + 1;
    if (mod == 3) {
        rm->is_reg = true;
        rm->reg = raw_rm | ((rex & 0x1) ? 8 : 0);
        if (rex == 0 && raw_rm >= 4)
            rm->reg |= X86_64_HIGH8_MARK;
'''
if old not in s:
    raise SystemExit("ModRM register decode anchor not found")
s = s.replace(old, new, 1)

p.write_text(s)
print("patched x86_64 legacy AH/CH/DH/BH byte-register decoding")
