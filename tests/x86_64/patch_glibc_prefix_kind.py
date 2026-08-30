#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()

# The base decoder historically tracked F2/F3 as a boolean because REP/REPE
# string handling only needed to know whether a repeat prefix was present.
# SSE/SSE2 reuses those bytes as mandatory opcode prefixes, so collapsing F2
# and F3 to `true` makes instructions such as SUBSD/SUBSS impossible to
# distinguish. Keep the actual prefix byte while preserving truthy checks used
# by the older REP paths.
decl_old = "        bool rep_prefix = false;\n"
decl_new = "        uint8_t rep_prefix = 0;\n"
f3_old = "            if (op == 0xf3) { rep_prefix = true; ip++; continue; }\n"
f3_new = "            if (op == 0xf3) { rep_prefix = op; ip++; continue; }\n"
f2_old = "            if (op == 0xf2) { rep_prefix = true; ip++; continue; }\n"
f2_new = "            if (op == 0xf2) { rep_prefix = op; ip++; continue; }\n"

counts = {
    "declaration": s.count(decl_old),
    "F3 parser": s.count(f3_old),
    "F2 parser": s.count(f2_old),
}
if not all(counts.values()):
    raise SystemExit(f"prefix decoder anchor missing: {counts}")

s = s.replace(decl_old, decl_new)
s = s.replace(f3_old, f3_new)
s = s.replace(f2_old, f2_new)
path.write_text(s)

print(
    "patched x86_64 mandatory-prefix state: "
    f"{counts['declaration']} decoder(s), preserving F2/F3 identity"
)
