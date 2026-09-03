#!/usr/bin/env python3
from pathlib import Path

path = Path("kernel/fork.c")
s = path.read_text()
if '#include <stdio.h>\n' not in s:
    s = s.replace('#include <stddef.h>\n', '#include <stddef.h>\n#include <stdio.h>\n', 1)
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
#if defined(GUEST_X86_64)
        // glibc expects the TCB head's first machine word to point back to the
        // TCB. Keep the write explicitly 64-bit for newly cloned threads.
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
clone3_anchor = """    // pidfd is an output address and glibc may initialize it even when
    // CLONE_PIDFD is absent. It is semantically ignored in that case.
    if (args.set_tid != 0 || args.set_tid_size != 0 || args.cgroup != 0)
        return _EINVAL;
"""
clone3_trace = """#ifdef GUEST_X86_64
    fprintf(stderr,
            "[vmine-clone3-args] flags=%llx pidfd=%llx child_tid=%llx parent_tid=%llx "
            "exit_signal=%llx stack=%llx stack_size=%llx tls=%llx set_tid=%llx "
            "set_tid_size=%llx cgroup=%llx\\n",
            (unsigned long long)args.flags, (unsigned long long)args.pidfd,
            (unsigned long long)args.child_tid, (unsigned long long)args.parent_tid,
            (unsigned long long)args.exit_signal, (unsigned long long)args.stack,
            (unsigned long long)args.stack_size, (unsigned long long)args.tls,
            (unsigned long long)args.set_tid, (unsigned long long)args.set_tid_size,
            (unsigned long long)args.cgroup);
#endif
    if (args.pidfd != 0 || args.set_tid != 0 || args.set_tid_size != 0 || args.cgroup != 0)
        return _EINVAL;
"""
if clone3_anchor not in s:
    raise SystemExit("clone3 validation anchor missing")
path.write_text(s.replace(clone3_anchor, clone3_trace, 1))
print("patched clone to install direct x86_64 FS TLS pointers")
