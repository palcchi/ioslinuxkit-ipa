from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
if '#include <stdio.h>' not in s:
    s = s.replace('#include <string.h>\n', '#include <string.h>\n#include <stdio.h>\n', 1)

old = '''            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOV r/m, immediate.
'''
new = '''            // Temporary bring-up trace for the Jammy loader relocation frame.
            // These encodings are the store/load pair around ld.so +0x10fa2.
            if ((op == 0x89 || op == 0x8b) && !rm.is_reg) {
                uint8_t m = 0, d0 = 0;
                (void)fetch_u8(cpu, ip + 1, &m);
                if (m == 0x85 || m == 0xb5) {
                    (void)fetch_u8(cpu, ip + 2, &d0);
                    if (d0 == 0x38) {
                        uint64_t memv = 0;
                        (void)guest_read(cpu, rm.addr, &memv, sizeof(memv));
                        fprintf(stderr, "[x86-frame-mov] pc=%llx op=%02x modrm=%02x rbp=%llx addr=%llx rax=%llx rsi=%llx mem=%llx\\n",
                                (unsigned long long)insn_start, op, m,
                                (unsigned long long)x86_64_get_reg(cpu, X86_64_RBP),
                                (unsigned long long)rm.addr,
                                (unsigned long long)x86_64_get_reg(cpu, X86_64_RAX),
                                (unsigned long long)x86_64_get_reg(cpu, X86_64_RSI),
                                (unsigned long long)memv);
                    }
                }
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOV r/m, immediate.
'''
if old not in s:
    raise SystemExit("MOV completion anchor not found")
s = s.replace(old, new, 1)

old = '''            write_reg_bits(cpu, reg, rm.addr, bits);
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOVSXD'''
new = '''            write_reg_bits(cpu, reg, rm.addr, bits);
            uint8_t lm = 0, ld = 0;
            (void)fetch_u8(cpu, ip + 1, &lm);
            (void)fetch_u8(cpu, ip + 2, &ld);
            if (lm == 0x45 && (ld == 0x90 || ld == 0xd0)) {
                fprintf(stderr, "[x86-frame-lea] pc=%llx disp=%02x rbp=%llx ea=%llx rax=%llx\\n",
                        (unsigned long long)insn_start, ld,
                        (unsigned long long)x86_64_get_reg(cpu, X86_64_RBP),
                        (unsigned long long)rm.addr,
                        (unsigned long long)x86_64_get_reg(cpu, X86_64_RAX));
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOVSXD'''
if old not in s:
    raise SystemExit("LEA completion anchor not found")
s = s.replace(old, new, 1)
p.write_text(s)
print("patched targeted Jammy loader relocation-frame trace")
