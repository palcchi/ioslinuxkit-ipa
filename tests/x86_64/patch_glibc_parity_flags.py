from pathlib import Path

cpu_h = Path("emu/arch/x86_64/cpu.h")
s = cpu_h.read_text()
old = '''    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t vf;
'''
new = '''    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t vf;
    uint8_t pf;
'''
if old not in s:
    raise SystemExit("cpu flag fields anchor not found")
s = s.replace(old, new, 1)
old = '''    if (cpu->cf) f |= 1ULL << 0; else f &= ~(1ULL << 0);
    if (cpu->zf) f |= 1ULL << 6; else f &= ~(1ULL << 6);
'''
new = '''    if (cpu->cf) f |= 1ULL << 0; else f &= ~(1ULL << 0);
    if (cpu->pf) f |= 1ULL << 2; else f &= ~(1ULL << 2);
    if (cpu->zf) f |= 1ULL << 6; else f &= ~(1ULL << 6);
'''
if old not in s:
    raise SystemExit("collapse flags anchor not found")
s = s.replace(old, new, 1)
old = '''    cpu->cf = (cpu->rflags >> 0) & 1;
    cpu->zf = (cpu->rflags >> 6) & 1;
'''
new = '''    cpu->cf = (cpu->rflags >> 0) & 1;
    cpu->pf = (cpu->rflags >> 2) & 1;
    cpu->zf = (cpu->rflags >> 6) & 1;
'''
if old not in s:
    raise SystemExit("expand flags anchor not found")
s = s.replace(old, new, 1)
cpu_h.write_text(s)

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
old = '''static uint64_t sign_bit(unsigned bits) {
    return 1ULL << (bits - 1);
}

static void set_logic_flags'''
new = '''static uint64_t sign_bit(unsigned bits) {
    return 1ULL << (bits - 1);
}

static uint8_t parity_even8(uint64_t value) {
    uint8_t v = (uint8_t)value;
    v ^= v >> 4;
    v &= 0x0f;
    // 0x6996 has a 1 for odd parity; x86 PF is set for even parity.
    return !((0x6996u >> v) & 1u);
}

static void set_logic_flags'''
if old not in s:
    raise SystemExit("sign_bit anchor not found")
s = s.replace(old, new, 1)

old = '''    cpu->zf = v == 0;
    cpu->nf = (v & sign_bit(bits)) != 0;
    cpu->cf = 0;
'''
new = '''    cpu->zf = v == 0;
    cpu->nf = (v & sign_bit(bits)) != 0;
    cpu->pf = parity_even8(v);
    cpu->cf = 0;
'''
if old not in s:
    raise SystemExit("logic flags anchor not found")
s = s.replace(old, new, 1)

# The same zf/nf pair appears in add and sub after the logic replacement.
old = '''    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
'''
new = '''    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->pf = parity_even8(result);
    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
'''
if old not in s:
    raise SystemExit("add flags anchor not found")
s = s.replace(old, new, 1)
old = '''    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
'''
new = '''    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->pf = parity_even8(result);
    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
'''
if old not in s:
    raise SystemExit("sub flags anchor not found")
s = s.replace(old, new, 1)

old = '''        // PF is not exposed in cpu_state yet. Conservative values keep the
        // decoder deterministic until parity-flag support lands.
        case 0x8: return false;                           // S? actually cc=8 is S
        case 0x9: return true;                            // NS
        case 0xa: return false;                           // P/PE
        case 0xb: return true;                            // NP/PO
'''
new = '''        case 0x8: return cpu->nf;                         // S
        case 0x9: return !cpu->nf;                        // NS
        case 0xa: return cpu->pf;                         // P/PE
        case 0xb: return !cpu->pf;                        // NP/PO
'''
if old not in s:
    raise SystemExit("condition parity/sign anchor not found")
s = s.replace(old, new, 1)

# Shift groups explicitly set ZF/SF. Make PF follow the result as x86 requires.
s = s.replace('''                cpu->zf = (result & bits_mask(bits)) == 0;
                cpu->nf = (result & sign_bit(bits)) != 0;
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
''', '''                cpu->zf = (result & bits_mask(bits)) == 0;
                cpu->nf = (result & sign_bit(bits)) != 0;
                cpu->pf = parity_even8(result);
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
''')

p.write_text(s)
print("patched x86_64 parity flag plus S/NS/P/NP conditions")
