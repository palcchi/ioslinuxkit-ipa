#!/usr/bin/env python3
from pathlib import Path

path = Path("kernel/exec.c")
s = path.read_text()

old_platform = '    addr_t platform_addr = sp = copy_string(sp, "aarch64");\n'
new_platform = '''#ifdef GUEST_X86_64
    addr_t platform_addr = sp = copy_string(sp, "x86_64");
#else
    addr_t platform_addr = sp = copy_string(sp, "aarch64");
#endif
'''
if old_platform not in s:
    raise SystemExit("platform string anchor missing")
s = s.replace(old_platform, new_platform, 1)

old_hwcap = '''        {AX_HWCAP, 0x003}, // FP|ASIMD only. Keep optional crypto/LSE features hidden until helper coverage is clean.
'''
new_hwcap = '''#ifdef GUEST_X86_64
        // x86_64 glibc primarily derives CPU features from CPUID. Do not feed it
        // ARM64 HWCAP bits through AT_HWCAP while the direct interpreter is
        // intentionally exposing only a conservative baseline CPU.
        {AX_HWCAP, 0},
#else
        {AX_HWCAP, 0x003}, // FP|ASIMD only. Keep optional crypto/LSE features hidden until helper coverage is clean.
#endif
'''
if old_hwcap not in s:
    raise SystemExit("HWCAP anchor missing")
s = s.replace(old_hwcap, new_hwcap, 1)

old_reset = '''    // Zero all general-purpose registers
    memset(current->cpu.regs, 0, sizeof(current->cpu.regs));
    current->cpu.nzcv = 0;
'''
new_reset = '''    // Zero the architectural register bank for the selected guest. The shared
    // regs[] view is still cleared because the compatibility syscall bridge
    // uses it, but x86_64 execution itself lives in x86_regs[].
    memset(current->cpu.regs, 0, sizeof(current->cpu.regs));
#ifdef GUEST_X86_64
    memset(current->cpu.x86_regs, 0, sizeof(current->cpu.x86_regs));
    current->cpu.rflags = 0x2;
    current->cpu.tls_ptr = 0;
    current->cpu.x86_syscall_pending = false;
    current->cpu.x86_last_syscall = 0;
#endif
    current->cpu.nzcv = 0;
'''
if old_reset not in s:
    raise SystemExit("CPU reset anchor missing")
s = s.replace(old_reset, new_reset, 1)

path.write_text(s)
print("patched x86_64 exec ABI platform/auxv/reset")
