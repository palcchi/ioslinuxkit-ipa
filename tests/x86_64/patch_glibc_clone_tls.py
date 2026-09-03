#!/usr/bin/env python3
from pathlib import Path

path = Path("kernel/fork.c")
s = path.read_text()
old = """#if defined(GUEST_ARM64)
        // On ARM64, the TLS argument is the actual TLS pointer value (for TPIDR_EL0),
        // not a pointer to a descriptor structure.
        task->cpu.tls_ptr = tls_addr;
#else
        err = task_set_thread_area(task, tls_addr);
"""
new = """#if defined(GUEST_ARM64) || defined(GUEST_X86_64)
        // ARM64 and Linux x86_64 clone pass the actual thread-pointer value.
        // Only the legacy i386 ABI passes a user_desc descriptor here.
        task->cpu.tls_ptr = tls_addr;
#else
        err = task_set_thread_area(task, tls_addr);
"""
if old not in s:
    raise SystemExit("clone TLS ABI anchor missing")
path.write_text(s.replace(old, new, 1))
print("patched clone to install direct x86_64 FS TLS pointers")
