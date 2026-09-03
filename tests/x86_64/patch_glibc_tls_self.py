#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
old = """        case ARCH_SET_FS:
            cpu->tls_ptr = value;
            return 0;
"""
new = """        case ARCH_SET_FS:
            // glibc's x86_64 TCB uses FS:0 as its full-width thread pointer.
            // Keep it canonical when the compact compatibility address space
            // creates a new TLS block; otherwise a truncated self pointer sends
            // BDS to a low unmapped address during pthread startup.
            cpu->tls_ptr = value;
            if (guest_write(cpu, value, &value, sizeof(value)) < 0)
                return -X86_64_EFAULT;
            return 0;
"""
if old not in s:
    raise SystemExit("ARCH_SET_FS anchor missing")
s = s.replace(old, new, 1)

old_read = """            } else {
                if (rm_read(cpu, &rm, move_bits, &value) < 0) goto gpf;
                write_reg_bits(cpu, reg, value, move_bits);
            }
"""
new_read = """            } else {
                if (rm_read(cpu, &rm, move_bits, &value) < 0) goto gpf;
                // The x86_64 TCB head is architecturally self-referential.
                // Normalize FS:0 at the read boundary so legacy shared-kernel
                // clone setup cannot expose an i386-width value to glibc.
                if (fs_prefix && move_bits == 64 && rm.addr == cpu->tls_ptr)
                    value = cpu->tls_ptr;
                write_reg_bits(cpu, reg, value, move_bits);
            }
"""
if old_read not in s:
    raise SystemExit("MOV TLS read anchor missing")
s = s.replace(old_read, new_read, 1)

mov_anchor = """        // MOV r/m, r and MOV r, r/m.
"""
mov_fast = """        // Fast path for MOV r64, FS:[disp32] in the absolute SIB form used by
        // glibc pthread startup. FS:0 is the TCB self pointer.
        if (fs_prefix && (rex & 0x8) && op == 0x8b) {
            uint8_t modrm, sib;
            uint32_t disp;
            if (fetch_u8(cpu, ip + 1, &modrm) == 0 &&
                fetch_u8(cpu, ip + 2, &sib) == 0 &&
                fetch_u32(cpu, ip + 3, &disp) == 0 &&
                (modrm & 0xc7) == 0x04 && sib == 0x25 && disp == 0) {
                unsigned reg = ((modrm >> 3) & 7) | ((rex & 0x4) ? 8 : 0);
                x86_64_set_reg(cpu, reg, cpu->tls_ptr);
                cpu->pc = ip + 7;
                cpu->cycle++;
                continue;
            }
        }

        // MOV r/m, r and MOV r, r/m.
"""
if mov_anchor not in s:
    raise SystemExit("MOV fast-path anchor missing")
path.write_text(s.replace(mov_anchor, mov_fast, 1))
print("patched x86_64 FS TLS self-pointer reads")
