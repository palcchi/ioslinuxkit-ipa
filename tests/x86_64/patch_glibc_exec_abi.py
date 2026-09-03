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

# BDS discovers its resource root with x86_64 readlink(2) on /proc/self/exe.
# The shared kernel exposes AArch64 readlinkat(2), whose argument layout differs.
interp = Path("emu/arch/x86_64/interp.c")
i = interp.read_text()
include_anchor = '''#include <string.h>\n'''
if include_anchor not in i:
    raise SystemExit("time include anchor missing")
i = i.replace(include_anchor, '''#include <string.h>
#include <time.h>
''', 1)
nr_anchor = '''        case 80:  return 49;   // chdir\n'''
nr_replace = '''        case 80:  return 49;   // chdir
        case 4:   return 79;   // stat -> newfstatat adapter
        case 21:  return 48;   // access -> faccessat adapter
        case 83:  return 34;   // mkdir -> mkdirat adapter
        case 89:  return 78;   // readlink -> readlinkat adapter
        case 99:  return 179;  // sysinfo
        case 131: return 132;  // sigaltstack
        case 137: return 43;   // statfs
        case 143: return 121;  // sched_getparam
        case 144: return 119;  // sched_setscheduler
        case 145: return 120;  // sched_getscheduler
        case 157: return 167;  // prctl
        case 191: return 8;    // getxattr
        case 192: return 9;    // lgetxattr
        case 204: return 123;  // sched_getaffinity
'''
if nr_anchor not in i:
    raise SystemExit("readlink syscall-number anchor missing")
i = i.replace(nr_anchor, nr_replace, 1)

bridge_anchor = '''    cpu->regs[8] = (uint64_t) compat_nr;
    cpu->regs[0] = x86_64_get_reg(cpu, X86_64_RDI);
    cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RSI);
    cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RDX);
    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);
'''
bridge_replace = '''    cpu->regs[8] = (uint64_t) compat_nr;
    if (guest_nr == 4) {
        cpu->regs[0] = (uint64_t)(int64_t)-100;
        cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RDI);
        cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RSI);
        cpu->regs[3] = cpu->regs[4] = cpu->regs[5] = 0;
    } else if (guest_nr == 21 || guest_nr == 83) {
        cpu->regs[0] = (uint64_t)(int64_t)-100;
        cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RDI);
        cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RSI);
        cpu->regs[3] = cpu->regs[4] = cpu->regs[5] = 0;
    } else if (guest_nr == 89) {
        cpu->regs[0] = (uint64_t)(int64_t)-100;
        cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RDI);
        cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RSI);
        cpu->regs[3] = x86_64_get_reg(cpu, X86_64_RDX);
        cpu->regs[4] = cpu->regs[5] = 0;
    } else {
        cpu->regs[0] = x86_64_get_reg(cpu, X86_64_RDI);
        cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RSI);
        cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RDX);
        cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
        cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
        cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);
    }
'''
if bridge_anchor not in i:
    raise SystemExit("readlink bridge anchor missing")
i = i.replace(bridge_anchor, bridge_replace, 1)

time_anchor = '''                // arch_prctl has no AArch64 syscall-table counterpart. Handle
                // the x86_64 FS bootstrap in the interpreter itself.
                if (guest_nr == 158) {
'''
time_replace = '''                // time(2) has no AArch64 syscall-table counterpart.
                if (guest_nr == 201) {
                    time_t now = time(NULL);
                    uint64_t out = (uint64_t)(int64_t)now;
                    uint64_t addr = x86_64_get_reg(cpu, X86_64_RDI);
                    if (addr && guest_write(cpu, addr, &out, sizeof(out)) < 0)
                        out = (uint64_t)(int64_t)-X86_64_EFAULT;
                    x86_64_set_rax(cpu, out);
                    continue;
                }

                // arch_prctl has no AArch64 syscall-table counterpart. Handle
                // the x86_64 FS bootstrap in the interpreter itself.
                if (guest_nr == 158) {
'''
if time_anchor not in i:
    raise SystemExit("time syscall anchor missing")
i = i.replace(time_anchor, time_replace, 1)
interp.write_text(i)

test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
func_anchor = '''static void test_write_exit(void) {\n'''
func = r'''static void test_readlink_bridge(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0xb8,0x59,0x00,0x00,0x00, // mov eax, 89 (readlink)
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RDI, BASE + 0x100);
    x86_64_set_reg(&cpu, X86_64_RSI, BASE + 0x200);
    x86_64_set_reg(&cpu, X86_64_RDX, 256);
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.regs[8] == 78);
    assert(cpu.regs[0] == (uint64_t)(int64_t)-100);
    assert(cpu.regs[1] == BASE + 0x100);
    assert(cpu.regs[2] == BASE + 0x200);
    assert(cpu.regs[3] == 256);
    puts("DIRECT X86_64 READLINK BRIDGE: PASS");
}

'''
if func_anchor not in t:
    raise SystemExit("readlink smoke function anchor missing")
t = t.replace(func_anchor, func + func_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("readlink smoke main anchor missing")
t = t.replace(main_anchor, '''    test_readlink_bridge();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 exec ABI and readlink compatibility for BDS resource discovery")
