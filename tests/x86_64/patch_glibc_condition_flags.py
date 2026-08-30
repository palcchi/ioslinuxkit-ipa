#!/usr/bin/env python3
from pathlib import Path
import re

cpu_path = Path("emu/arch/x86_64/cpu.h")
interp_path = Path("emu/arch/x86_64/interp.c")

cpu = cpu_path.read_text()
interp = interp_path.read_text()

# x86_64 condition codes used by glibc/BDS need the architectural parity flag.
# The existing smoke coverage already checks cpu.pf for UCOMISS/UCOMISD, but the
# x86_64 cpu_state had no PF storage and PUSHF/POPF helpers did not preserve it.
pf_anchor = "    uint8_t cf;\n    uint8_t vf;\n"
pf_replacement = "    uint8_t cf;\n    uint8_t pf;\n    uint8_t vf;\n"
if pf_anchor in cpu:
    cpu = cpu.replace(pf_anchor, pf_replacement, 1)
elif "    uint8_t pf;\n" not in cpu:
    raise SystemExit("cpu_state PF anchor missing")

collapse_anchor = "    if (cpu->cf) f |= 1ULL << 0; else f &= ~(1ULL << 0);\n    if (cpu->zf) f |= 1ULL << 6; else f &= ~(1ULL << 6);\n"
collapse_replacement = "    if (cpu->cf) f |= 1ULL << 0; else f &= ~(1ULL << 0);\n    if (cpu->pf) f |= 1ULL << 2; else f &= ~(1ULL << 2);\n    if (cpu->zf) f |= 1ULL << 6; else f &= ~(1ULL << 6);\n"
if collapse_anchor in cpu:
    cpu = cpu.replace(collapse_anchor, collapse_replacement, 1)
elif "if (cpu->pf) f |= 1ULL << 2" not in cpu:
    raise SystemExit("collapse_flags PF anchor missing")

expand_anchor = "    cpu->cf = (cpu->rflags >> 0) & 1;\n    cpu->zf = (cpu->rflags >> 6) & 1;\n"
expand_replacement = "    cpu->cf = (cpu->rflags >> 0) & 1;\n    cpu->pf = (cpu->rflags >> 2) & 1;\n    cpu->zf = (cpu->rflags >> 6) & 1;\n"
if expand_anchor in cpu:
    cpu = cpu.replace(expand_anchor, expand_replacement, 1)
elif "cpu->pf = (cpu->rflags >> 2) & 1" not in cpu:
    raise SystemExit("expand_flags PF anchor missing")

# PF is even parity of the low byte of the result. Glibc uses JP/JNP in several
# optimized paths, and pretending PF is constant can silently select the wrong
# implementation instead of producing an obvious illegal-instruction trap.
helper_anchor = "static uint64_t sign_bit(unsigned bits) {\n    return 1ULL << (bits - 1);\n}\n\n"
helper = "static uint64_t sign_bit(unsigned bits) {\n    return 1ULL << (bits - 1);\n}\n\nstatic uint8_t parity_even8(uint8_t value) {\n    value ^= value >> 4;\n    value &= 0x0f;\n    return (0x9669U >> value) & 1U;\n}\n\nstatic void set_result_parity(struct cpu_state *cpu, uint64_t value) {\n    cpu->pf = parity_even8((uint8_t)value);\n}\n\n"
if helper_anchor in interp:
    interp = interp.replace(helper_anchor, helper, 1)
elif "static uint8_t parity_even8" not in interp:
    raise SystemExit("parity helper anchor missing")

logic_anchor = "    cpu->nf = (v & sign_bit(bits)) != 0;\n    cpu->cf = 0;\n    cpu->vf = 0;\n"
logic_replacement = "    cpu->nf = (v & sign_bit(bits)) != 0;\n    set_result_parity(cpu, v);\n    cpu->cf = 0;\n    cpu->vf = 0;\n"
if logic_anchor in interp:
    interp = interp.replace(logic_anchor, logic_replacement, 1)
elif "set_result_parity(cpu, v);" not in interp:
    raise SystemExit("logic parity anchor missing")

add_anchor = "    cpu->zf = result == 0;\n    cpu->nf = (result & sign_bit(bits)) != 0;\n    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;\n"
add_replacement = "    cpu->zf = result == 0;\n    cpu->nf = (result & sign_bit(bits)) != 0;\n    set_result_parity(cpu, result);\n    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;\n"
if add_anchor in interp:
    interp = interp.replace(add_anchor, add_replacement, 1)
elif interp.count("set_result_parity(cpu, result);") < 1:
    raise SystemExit("add parity anchor missing")

sub_anchor = "    cpu->cf = aa < bb;\n    cpu->zf = result == 0;\n    cpu->nf = (result & sign_bit(bits)) != 0;\n    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;\n"
sub_replacement = "    cpu->cf = aa < bb;\n    cpu->zf = result == 0;\n    cpu->nf = (result & sign_bit(bits)) != 0;\n    set_result_parity(cpu, result);\n    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;\n"
if sub_anchor in interp:
    interp = interp.replace(sub_anchor, sub_replacement, 1)
elif interp.count("set_result_parity(cpu, result);") < 2:
    raise SystemExit("sub parity anchor missing")

condition_replacement = "        case 0x8: return cpu->nf;                         // S\n        case 0x9: return !cpu->nf;                        // NS\n        case 0xa: return cpu->pf;                         // P/PE\n        case 0xb: return !cpu->pf;                        // NP/PO\n"
if "case 0xa: return cpu->pf" not in interp:
    condition_pattern = re.compile(
        r"(?:\s*//[^\n]*\n){0,3}"
        r"\s*case 0x8:\s*return [^;]+;[^\n]*\n"
        r"\s*case 0x9:\s*return [^;]+;[^\n]*\n"
        r"\s*case 0xa:\s*return [^;]+;[^\n]*\n"
        r"\s*case 0xb:\s*return [^;]+;[^\n]*\n"
    )
    interp, replaced = condition_pattern.subn("\n" + condition_replacement, interp, count=1)
    if replaced != 1:
        raise SystemExit("condition-code PF/SF anchor missing")

cpu_path.write_text(cpu)
interp_path.write_text(interp)

print("patched x86_64 SF/PF condition handling for glibc/BDS")
