#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()

anchor = '''        // MOV r64, imm64 / MOV r32, imm32.\n        if (op >= 0xb8 && op <= 0xbf) {\n'''
insert = '''        // MOV r8, imm8 (B0-B7). Without REX, encodings 4..7 are\n        // AH/CH/DH/BH. With any REX prefix they become SPL/BPL/SIL/DIL,\n        // and REX.B extends the whole B0-B7 range to r8b-r15b.\n        if (op >= 0xb0 && op <= 0xb7) {\n            uint8_t imm;\n            if (fetch_u8(cpu, ip + 1, &imm) < 0) goto gpf;\n            unsigned raw_reg = op - 0xb0;\n            unsigned reg = raw_reg | ((rex & 0x1) ? 8 : 0);\n            if (rex == 0 && raw_reg >= 4)\n                reg |= X86_64_HIGH8_MARK;\n            write_reg_bits(cpu, reg, imm, 8);\n            cpu->pc = ip + 2;\n            cpu->cycle++;\n            continue;\n        }\n\n'''

if anchor not in s:
    raise SystemExit("MOV immediate anchor not found")
s = s.replace(anchor, insert + anchor, 1)
p.write_text(s)
print("patched x86_64 interpreter with MOV r8, imm8")
