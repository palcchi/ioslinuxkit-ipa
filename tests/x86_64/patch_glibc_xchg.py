#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''        // MOV r64, imm64 / MOV r32, imm32.\n'''
insert = r'''        // 90+rd: XCHG rAX, r. Bare 90 is the architectural NOP; the
        // remaining compact forms are still emitted by glibc startup code.
        if (op >= 0x90 && op <= 0x97) {
            unsigned reg = (op - 0x90) | ((rex & 0x1) ? 8 : 0);
            if (op == 0x90 && reg == X86_64_RAX) {
                cpu->pc = ip + 1;
                cpu->cycle++;
                continue;
            }
            uint64_t a = read_reg_bits(cpu, X86_64_RAX, bits);
            uint64_t b = read_reg_bits(cpu, reg, bits);
            write_reg_bits(cpu, X86_64_RAX, b, bits);
            write_reg_bits(cpu, reg, a, bits);
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // 87 /r: XCHG r/m16/32/64, r. The memory form is architecturally
        // atomic, but the guest interpreter is single-step serialized here;
        // ordinary load/store exchange is enough for current loader bring-up.
        if (op == 0x87) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            uint64_t rm_value, reg_value;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            if (rm_read(cpu, &rm, bits, &rm_value) < 0) goto gpf;
            reg_value = read_reg_bits(cpu, reg, bits);
            if (rm_write(cpu, &rm, bits, reg_value) < 0) goto gpf;
            write_reg_bits(cpu, reg, rm_value, bits);
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

'''
if anchor not in s:
    raise SystemExit("MOV immediate anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with XCHG forms")
