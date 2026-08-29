#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()

anchor = '''            // Multi-byte NOP (0F 1F /0).\n            if (op2 == 0x1f) {\n'''
insert = '''            // MOVNTDQ m128, xmm (66 0F E7 /r). For the interpreter, the\n            // non-temporal cache policy is irrelevant; architecturally the\n            // visible effect is the same 16-byte store.\n            if (operand16 && op2 == 0xe7) {\n                struct rm_operand rm;\n                unsigned xmm;\n                addr_t next;\n                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;\n                if (rm.is_reg) goto undefined;\n                if (guest_write(cpu, rm.addr, &cpu->xmm[xmm & 15], 16) < 0) goto gpf;\n                cpu->pc = next;\n                cpu->cycle++;\n                continue;\n            }\n\n'''

if anchor not in s:
    raise SystemExit("0F 1F anchor missing")
if "MOVNTDQ m128, xmm" in s:
    raise SystemExit("MOVNTDQ handler already present")
s = s.replace(anchor, insert + anchor, 1)
p.write_text(s)
print("patched x86_64 MOVNTDQ m128,xmm store")
