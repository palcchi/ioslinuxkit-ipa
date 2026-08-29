#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
insert = r'''        // Byte form of the F6 group: TEST r/m8, imm8 plus NOT/NEG.
        // The loader uses compact byte flag probes in feature-selection code.
        if (op == 0xf6) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned group_raw = (modrm >> 3) & 7;
            unsigned imm_bytes = group_raw == 0 ? 1 : 0;
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            uint64_t value;
            if (rm_read(cpu, &rm, 8, &value) < 0) goto gpf;
            switch (group & 7) {
                case 0: {
                    uint8_t imm;
                    if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                    set_logic_flags(cpu, value & imm, 8);
                    break;
                }
                case 2:
                    if (rm_write(cpu, &rm, 8, ~value) < 0) goto gpf;
                    break;
                case 3: {
                    uint64_t result = set_sub_flags(cpu, 0, value, 8);
                    if (rm_write(cpu, &rm, 8, result) < 0) goto gpf;
                    break;
                }
                default:
                    goto undefined;
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("F7 anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with F6 byte group")
