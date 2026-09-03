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
path.write_text(s.replace(old_read, new_read, 1))
print("patched x86_64 FS TLS self-pointer reads")
