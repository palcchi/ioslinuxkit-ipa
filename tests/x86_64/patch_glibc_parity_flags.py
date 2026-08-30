from pathlib import Path
import re

cpu_h = Path("emu/arch/x86_64/cpu.h")
s = cpu_h.read_text()

# This patch predates patch_glibc_condition_flags.py. Keep it idempotent so the
# two compatibility layers can coexist while the bring-up patch stack is still
# being consolidated.
if "    uint8_t pf;\n" not in s:
    old = '''    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t vf;
'''
    new = '''    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t pf;
    uint8_t vf;
'''
    if old not in s:
        raise SystemExit("cpu flag fields anchor not found")
    s = s.replace(old, new, 1)

if "if (cpu->pf) f |= 1ULL << 2" not in s:
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

if "cpu->pf = (cpu->rflags >> 2) & 1" not in s:
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

# Reuse whichever parity helper an earlier patch installed. Only install the
# legacy helper when no parity implementation exists yet.
if "static uint8_t parity_even8" not in s:
    old = '''static uint64_t sign_bit(unsigned bits) {
    return 1ULL << (bits - 1);
}

static void set_logic_flags'''
    new = '''static uint64_t sign_bit(unsigned bits) {
    return 1ULL << (bits - 1);
}

static uint8_t parity_even8(uint8_t value) {
    value ^= value >> 4;
    value &= 0x0f;
    return (0x9669U >> value) & 1U;
}

static void set_result_parity(struct cpu_state *cpu, uint64_t value) {
    cpu->pf = parity_even8((uint8_t)value);
}

static void set_logic_flags'''
    if old not in s:
        raise SystemExit("sign_bit anchor not found")
    s = s.replace(old, new, 1)

# Ensure condition-code arms are architecturally correct regardless of which
# earlier patch touched comments or spacing.
repls = {
    8: '        case 0x8: return cpu->nf;                         // S',
    9: '        case 0x9: return !cpu->nf;                        // NS',
    10: '        case 0xa: return cpu->pf;                         // P/PE',
    11: '        case 0xb: return !cpu->pf;                        // NP/PO',
}
for cc, line in repls.items():
    pat = rf'^\s*case 0x{cc:x}: return [^;]+;[^\n]*$'
    if re.search(pat, s, flags=re.M):
        s = re.sub(pat, line, s, count=1, flags=re.M)

# Shift groups explicitly update ZF/SF in the older decoder. Add PF where that
# exact sequence still exists. If a previous patch already added parity, leave
# it alone.
shift_old = '''                cpu->zf = (result & bits_mask(bits)) == 0;
                cpu->nf = (result & sign_bit(bits)) != 0;
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
'''
shift_new = '''                cpu->zf = (result & bits_mask(bits)) == 0;
                cpu->nf = (result & sign_bit(bits)) != 0;
                set_result_parity(cpu, result);
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
'''
if shift_old in s:
    s = s.replace(shift_old, shift_new)

p.write_text(s)
print("patched x86_64 parity flag plus S/NS/P/NP conditions")
