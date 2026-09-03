#!/usr/bin/env python3
from pathlib import Path

# x86_64 and AArch64 both use the 64-bit time ABI. The original non-ARM
# fallback is i386-style (two 32-bit fields), which corrupts clock_gettime
# output and futex absolute deadlines.
time_h = Path("kernel/time.h")
th = time_h.read_text()
time_anchor = '''#ifdef GUEST_ARM64
struct timeval_ {
'''
time_replace = '''#if defined(GUEST_ARM64) || defined(GUEST_X86_64)
struct timeval_ {
'''
if time_anchor not in th:
    raise SystemExit("64-bit time ABI anchor missing")
th = th.replace(time_anchor, time_replace, 1)
time_h.write_text(th)

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 31: RDTSC. A synthetic monotonic timestamp counter is
            // sufficient for userspace loader timing/entropy probes. It is tied
            // to emulated instruction progress rather than wall clock time so
            // execution stays deterministic across hosts.
            if (op2 == 0x31) {
                uint64_t tsc = ((uint64_t)cpu->cycle << 10) + step;
                write_reg_bits(cpu, X86_64_RAX, (uint32_t)tsc, 32);
                write_reg_bits(cpu, X86_64_RDX, (uint32_t)(tsc >> 32), 32);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }

            // 0F 40..4F /r: CMOVcc r, r/m. CMOV is part of the ordinary
            // x86-64 baseline and glibc uses it heavily in early loader code.
            if (op2 >= 0x40 && op2 <= 0x4f) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (condition_true(cpu, op2 & 15)) {
                    uint64_t value;
                    if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
                    write_reg_bits(cpu, reg, value, bits);
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 64-bit time ABI, RDTSC, and CMOVcc")
