#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // MOV r64, imm64 / MOV r32, imm32.\n'''
insert = r'''        // 68 id / 6A ib: PUSH immediate. In 64-bit mode both forms push
        // eight bytes; the immediate is sign-extended to 64 bits. glibc still
        // uses the compact imm8 form in ordinary loader code.
        if (op == 0x68 || op == 0x6a) {
            if (operand16)
                goto undefined; // 16-bit stack-width form is not needed yet.
            uint64_t value;
            if (op == 0x6a) {
                uint8_t imm;
                if (fetch_u8(cpu, ip + 1, &imm) < 0) goto gpf;
                value = (uint64_t)(int64_t)(int8_t)imm;
                cpu->pc = ip + 2;
            } else {
                uint32_t imm;
                if (fetch_u32(cpu, ip + 1, &imm) < 0) goto gpf;
                value = (uint64_t)(int64_t)(int32_t)imm;
                cpu->pc = ip + 5;
            }
            if (push_u64(cpu, value) < 0) goto gpf;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("MOV immediate anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with immediate PUSH forms")
