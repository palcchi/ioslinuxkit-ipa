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
        // Both 64-bit ABIs pass the actual thread pointer. Legacy i386 alone
        // passes a user_desc structure.
        task->cpu.tls_ptr = tls_addr;
#if defined(GUEST_X86_64)
        qword_t tls_self = (qword_t) tls_addr;
        if (user_write_task(task, tls_addr, &tls_self, sizeof(tls_self))) {
            err = _EFAULT;
            goto fail_free_sighand;
        }
#endif
#else
        err = task_set_thread_area(task, tls_addr);
"""
if old not in s:
    raise SystemExit("clone TLS ABI anchor missing")
s = s.replace(old, new, 1)

clone3_old = """    if (args.pidfd != 0 || args.set_tid != 0 || args.set_tid_size != 0 || args.cgroup != 0)
        return _EINVAL;
"""
clone3_new = """    // glibc initializes pidfd storage together with parent_tid even when
    // CLONE_PIDFD is absent; it is ignored in that case.
    if (args.set_tid != 0 || args.set_tid_size != 0 || args.cgroup != 0)
        return _EINVAL;
"""
if clone3_old not in s:
    raise SystemExit("clone3 validation anchor missing")
s = s.replace(clone3_old, clone3_new, 1)

ret_old = """    CPU_RETVAL(task->cpu) = 0;
"""
ret_new = """    CPU_RETVAL(task->cpu) = 0;
#ifdef GUEST_X86_64
    // The interpreter resumes from this compatibility return slot.
    task->cpu.regs[0] = 0;
#endif
"""
if ret_old not in s:
    raise SystemExit("clone child return anchor missing")
path.write_text(s.replace(ret_old, ret_new, 1))
print("patched direct x86_64 clone TLS, child return, and clone3 validation")
