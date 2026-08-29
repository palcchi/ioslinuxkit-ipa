#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()

old = '''            // Multi-byte NOP (0F 1F /0).\n            if (op2 == 0x1f) {\n'''
new = '''            // PREFETCHh (0F 18 /0..3). These are non-faulting cache hints.\n            // Decode the effective-address bytes so RIP advances correctly, but\n            // deliberately do not touch guest memory. The interpreter has no\n            // host-cache contract to satisfy for these hints.\n            if (op2 == 0x18) {\n                struct rm_operand rm;\n                unsigned hint;\n                addr_t next;\n                if (decode_rm(cpu, rex, false, ip + 2, 0, &rm, &hint, &next) < 0) goto gpf;\n                if (!rm.is_reg && hint <= 3) {\n                    cpu->pc = next;\n                    cpu->cycle++;\n                    continue;\n                }\n            }\n\n            // Multi-byte NOP (0F 1F /0).\n            if (op2 == 0x1f) {\n'''
if old not in s:
    raise SystemExit("0F 1F anchor missing")
s = s.replace(old, new, 1)

p.write_text(s)
print("patched x86_64 PREFETCHh as decoded non-faulting cache hint")
