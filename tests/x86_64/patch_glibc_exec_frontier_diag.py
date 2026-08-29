#!/usr/bin/env python3
from pathlib import Path

p = Path("kernel/exec.c")
s = p.read_text()

old = '''        interp_fd = generic_open(interp_name, O_RDONLY, 0);\n        if (IS_ERR(interp_fd)) {\n            err = PTR_ERR(interp_fd);\n            goto out_free_interp;\n        }'''
new = '''        interp_fd = generic_open(interp_name, O_RDONLY, 0);\n        if (IS_ERR(interp_fd)) {\n            err = PTR_ERR(interp_fd);\n#ifdef GUEST_X86_64\n            fprintf(stderr, "x86-exec: PT_INTERP open failed file=%s interp=%s err=%d (%s)\\n",\n                    file, interp_name, err, strerror(-err));\n#endif\n            goto out_free_interp;\n        }'''
if old not in s:
    raise SystemExit("PT_INTERP open block not found")
s = s.replace(old, new, 1)

old = '''    addr_t platform_addr = sp = copy_string(sp, "aarch64");\n    if (sp == 0)\n        goto out_free_interp;'''
new = '''#ifdef GUEST_X86_64\n    addr_t platform_addr = sp = copy_string(sp, "x86_64");\n#else\n    addr_t platform_addr = sp = copy_string(sp, "aarch64");\n#endif\n    if (sp == 0)\n        goto out_free_interp;'''
if old not in s:
    raise SystemExit("AT_PLATFORM block not found")
s = s.replace(old, new, 1)

old = '''        {AX_HWCAP, 0x003}, // FP|ASIMD only. Keep optional crypto/LSE features hidden until helper coverage is clean.'''
new = '''#ifdef GUEST_X86_64\n        // x86_64 feature discovery is exposed through CPUID. Do not leak the\n        // ARM64 FP/ASIMD HWCAP bits into the x86_64 ELF auxiliary vector.\n        {AX_HWCAP, 0},\n#else\n        {AX_HWCAP, 0x003}, // FP|ASIMD only. Keep optional crypto/LSE features hidden until helper coverage is clean.\n#endif'''
if old not in s:
    raise SystemExit("AT_HWCAP block not found")
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
print("patched x86_64 exec diagnostics + AT_PLATFORM/HWCAP")
