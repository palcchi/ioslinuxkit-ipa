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
path.write_text(s.replace(old, new, 1))
print("patched x86_64 ARCH_SET_FS with a canonical 64-bit TCB self pointer")
