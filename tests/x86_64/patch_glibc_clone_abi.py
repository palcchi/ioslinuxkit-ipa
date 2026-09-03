#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
old = """    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);
    cpu->x86_syscall_pending = true;
"""
new = """    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);

    // x86_64 clone: flags, stack, parent_tid, child_tid (r10), tls (r8).
    // Shared sys_clone: flags, stack, parent_tid, tls, child_tid.
    if (guest_nr == 56) {
        cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R8);
        cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R10);
    }
    cpu->x86_syscall_pending = true;
"""
if old not in s:
    raise SystemExit("syscall bridge anchor missing")
path.write_text(s.replace(old, new, 1))
print("patched x86_64 clone ABI TLS/child_tid argument order")
