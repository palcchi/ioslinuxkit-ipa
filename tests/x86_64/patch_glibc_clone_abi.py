#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
if '#include <stdio.h>\n' not in s:
    s = s.replace('#include <string.h>\n', '#include <string.h>\n#include <stdio.h>\n', 1)
old = """    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);
    cpu->x86_syscall_pending = true;
"""
new = """    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);

    // Linux x86_64 clone(flags, stack, parent_tid, child_tid, tls) places
    // child_tid in r10 and tls in r8. The shared AArch64 syscall table uses
    // clone(flags, stack, parent_tid, tls, child_tid), so swap arguments four
    // and five before entering sys_clone. Without this, new BDS threads use
    // child_tid as FS base and immediately fault at FS:[0].
    if (guest_nr == 56) {
        cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R8);
        cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R10);
        fprintf(stderr,
                "[vmine-clone-enter] flags=%llx stack=%llx ptid=%llx tls=%llx ctid=%llx\\n",
                (unsigned long long)cpu->regs[0],
                (unsigned long long)cpu->regs[1],
                (unsigned long long)cpu->regs[2],
                (unsigned long long)cpu->regs[3],
                (unsigned long long)cpu->regs[4]);
    } else if (guest_nr == 435) {
        fprintf(stderr,
                "[vmine-clone3-enter] args=%llx size=%llu\\n",
                (unsigned long long)cpu->regs[0],
                (unsigned long long)cpu->regs[1]);
    }
    cpu->x86_syscall_pending = true;
"""
if old not in s:
    raise SystemExit("syscall bridge anchor missing")
s = s.replace(old, new, 1)
resume_old = """    if (cpu->x86_syscall_pending) {
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }
"""
resume_new = """    if (cpu->x86_syscall_pending) {
        if (cpu->x86_last_syscall == 56 || cpu->x86_last_syscall == 435)
            fprintf(stderr, "[vmine-clone-return] nr=%llu result=%lld fs=%llx\\n",
                    (unsigned long long)cpu->x86_last_syscall,
                    (long long)cpu->regs[0],
                    (unsigned long long)cpu->tls_ptr);
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }
"""
if resume_old not in s:
    raise SystemExit("syscall resume anchor missing")
path.write_text(s.replace(resume_old, resume_new, 1))
print("patched x86_64 clone ABI TLS/child_tid argument order")
