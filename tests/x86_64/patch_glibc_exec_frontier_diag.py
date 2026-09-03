#!/usr/bin/env python3
from pathlib import Path

p = Path("kernel/exec.c")
s = p.read_text()

# patch_glibc_exec_abi.py runs earlier alphabetically and already fixes
# AT_PLATFORM/HWCAP/reset. This patch is deliberately diagnostic-only so the
# BDS frontier tells us whether ENOENT comes from the executable itself, its
# PT_INTERP, or a later ELF load stage.
old = '''        interp_fd = generic_open(interp_name, O_RDONLY, 0);\n        if (IS_ERR(interp_fd)) {\n            err = PTR_ERR(interp_fd);\n            goto out_free_interp;\n        }'''
new = '''        interp_fd = generic_open(interp_name, O_RDONLY, 0);\n        if (IS_ERR(interp_fd)) {\n            err = PTR_ERR(interp_fd);\n#ifdef GUEST_X86_64\n            fprintf(stderr, "x86-exec: PT_INTERP open failed file=%s interp=%s err=%d (%s)\\n",\n                    file, interp_name, err, strerror(-err));\n#endif\n            goto out_free_interp;\n        }'''
if old not in s:
    raise SystemExit("PT_INTERP open block not found")
s = s.replace(old, new, 1)

old = '''int __do_execve(const char *file, struct exec_args argv, struct exec_args envp) {\n    struct fd *fd = generic_open(file, O_RDONLY, 0);\n    if (IS_ERR(fd))\n        return PTR_ERR(fd);'''
new = '''int __do_execve(const char *file, struct exec_args argv, struct exec_args envp) {\n    struct fd *fd = generic_open(file, O_RDONLY, 0);\n    if (IS_ERR(fd)) {\n        int open_err = PTR_ERR(fd);\n#ifdef GUEST_X86_64\n        fprintf(stderr, "x86-exec: executable open failed file=%s err=%d (%s)\\n",\n                file, open_err, strerror(-open_err));\n#endif\n        return open_err;\n    }'''
if old not in s:
    raise SystemExit("__do_execve open block not found")
s = s.replace(old, new, 1)

old = '''    err = format_exec(fd, file, argv, envp);\n    if (err == _ENOEXEC)\n        err = shebang_exec(fd, file, argv, envp);\n    fd_close(fd);\n    if (err < 0)\n        return err;'''
new = '''    err = format_exec(fd, file, argv, envp);\n    if (err == _ENOEXEC)\n        err = shebang_exec(fd, file, argv, envp);\n    fd_close(fd);\n    if (err < 0) {\n#ifdef GUEST_X86_64\n        fprintf(stderr, "x86-exec: format/load failed file=%s err=%d (%s)\\n",\n                file, err, strerror(-err));\n#endif\n        return err;\n    }'''
if old not in s:
    raise SystemExit("format_exec result block not found")
s = s.replace(old, new, 1)

p.write_text(s)

# Keep runtime syscall diagnostics focused: report each unsupported x86_64
# syscall once, plus the result of resource discovery and network creation.
interp = Path("emu/arch/x86_64/interp.c")
i = interp.read_text()
missing_anchor = '''                if (compat_nr < 0) {
                    x86_64_set_rax(cpu, (uint64_t)(int64_t)-X86_64_ENOSYS);
                    continue;
                }
'''
missing_replace = '''                if (compat_nr < 0) {
                    static bool missing_seen[512];
                    if (guest_nr >= 512 || !missing_seen[guest_nr]) {
                        if (guest_nr < 512) missing_seen[guest_nr] = true;
                        fprintf(stderr, "vmine-x86-missing-syscall nr=%llu\\n",
                                (unsigned long long)guest_nr);
                    }
                    x86_64_set_rax(cpu, (uint64_t)(int64_t)-X86_64_ENOSYS);
                    continue;
                }
'''
if missing_anchor not in i:
    raise SystemExit("missing-syscall diagnostic anchor missing")
i = i.replace(missing_anchor, missing_replace, 1)

result_anchor = '''    if (cpu->x86_syscall_pending) {
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }
'''
result_replace = '''    if (cpu->x86_syscall_pending) {
        if (cpu->x86_last_syscall == 41 || cpu->x86_last_syscall == 49 ||
            cpu->x86_last_syscall == 89 || cpu->x86_last_syscall == 291) {
            fprintf(stderr, "vmine-x86-syscall nr=%llu result=%lld\\n",
                    (unsigned long long)cpu->x86_last_syscall,
                    (long long)cpu->regs[0]);
        }
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }
'''
if result_anchor not in i:
    raise SystemExit("syscall-result diagnostic anchor missing")
i = i.replace(result_anchor, result_replace, 1)
interp.write_text(i)

print("patched x86_64 exec and focused syscall frontier diagnostics")
