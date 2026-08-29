#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()

old = '''        bool fs_prefix = false;
        bool rep_prefix = false;
        bool operand16 = false;
        uint8_t rex = 0;
'''
new = '''        bool fs_prefix = false;
        bool rep_prefix = false;
        bool operand16 = false;
        bool lock_prefix = false;
        uint8_t rex = 0;
'''
if old not in s:
    raise SystemExit("prefix state declaration anchor missing")
s = s.replace(old, new, 1)

old = '''            if (op == 0x64) { fs_prefix = true; ip++; continue; }
            if (op == 0x66) { operand16 = true; ip++; continue; }
'''
new = '''            if (op == 0x64) { fs_prefix = true; ip++; continue; }
            if (op == 0xf0) { lock_prefix = true; ip++; continue; }
            if (op == 0x66) { operand16 = true; ip++; continue; }
'''
if old not in s:
    raise SystemExit("prefix parser anchor missing")
s = s.replace(old, new, 1)

anchor = '''            // SYSCALL.\n'''
insert = r'''            // CMPXCHG r/m,reg (0F B0 byte, 0F B1 word/dword/qword).
            // LOCK is naturally serialized by this direct interpreter; consume
            // the prefix but keep architectural compare/exchange semantics.
            if (op2 == 0xb0 || op2 == 0xb1) {
                unsigned width = op2 == 0xb0 ? 8 : bits;
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                uint64_t dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, width, &dst) < 0) goto gpf;
                uint64_t acc = read_reg_bits(cpu, X86_64_RAX, width);
                uint64_t src = read_reg_bits(cpu, reg, width);
                uint64_t cmp = set_sub_flags(cpu, acc, dst, width);
                (void)cmp;
                if ((acc & bits_mask(width)) == (dst & bits_mask(width))) {
                    cpu->zf = 1;
                    if (rm_write(cpu, &rm, width, src) < 0) goto gpf;
                } else {
                    cpu->zf = 0;
                    write_reg_bits(cpu, X86_64_RAX, dst, width);
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // XADD r/m,reg (0F C0 byte, 0F C1 word/dword/qword).
            if (op2 == 0xc0 || op2 == 0xc1) {
                unsigned width = op2 == 0xc0 ? 8 : bits;
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                uint64_t dst;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, width, &dst) < 0) goto gpf;
                uint64_t src = read_reg_bits(cpu, reg, width);
                uint64_t result = set_add_flags(cpu, dst, src, width);
                if (rm_write(cpu, &rm, width, result) < 0) goto gpf;
                write_reg_bits(cpu, reg, dst, width);
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F syscall anchor missing")
s = s.replace(anchor, insert + anchor, 1)

# The variable documents/consumes the architectural prefix even when the
# current instruction does not require special host synchronization.
old = '''        unsigned bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);\n'''
new = '''        (void)lock_prefix;
        unsigned bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);\n'''
if old not in s:
    raise SystemExit("operand-size anchor missing")
s = s.replace(old, new, 1)

p.write_text(s)
print("patched x86_64 LOCK prefix with CMPXCHG and XADD atomics")
