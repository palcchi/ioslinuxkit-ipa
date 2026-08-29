from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
old = '''            // CPUID: expose a conservative x86_64-v1-ish CPU. AVX/AVX2 are
            // deliberately hidden so glibc will not choose instruction paths we
            // have not implemented yet.
            if (op2 == 0xa2) {
                uint32_t leaf = (uint32_t)x86_64_get_rax(cpu);
                uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;
                if (leaf == 0) {
                    eax = 1;
                    ebx = 0x756e6547; // "Genu"
                    edx = 0x49656e69; // "ineI"
                    ecx = 0x6c65746e; // "ntel"
                } else if (leaf == 1) {
                    eax = 0x00000663;
                    // FPU, CX8, CMOV, MMX, FXSR, SSE, SSE2.
                    edx = (1u<<0) | (1u<<8) | (1u<<15) | (1u<<23) |
                          (1u<<24) | (1u<<25) | (1u<<26);
                    ecx = 0;
                }
                write_reg_bits(cpu, X86_64_RAX, eax, 32);
                write_reg_bits(cpu, X86_64_RBX, ebx, 32);
                write_reg_bits(cpu, X86_64_RCX, ecx, 32);
                write_reg_bits(cpu, X86_64_RDX, edx, 32);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }
'''
new = '''            // CPUID: expose a complete x86-64 baseline CPU while keeping
            // optional SIMD generations hidden.  In particular, glibc also
            // probes the extended leaves for long mode/SYSCALL even though the
            // process is already an ELF64 process.
            if (op2 == 0xa2) {
                uint32_t leaf = (uint32_t)x86_64_get_rax(cpu);
                uint32_t subleaf = (uint32_t)x86_64_get_reg(cpu, X86_64_RCX);
                uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;
                (void) subleaf;
                if (leaf == 0) {
                    eax = 1;
                    ebx = 0x756e6547; // "Genu"
                    edx = 0x49656e69; // "ineI"
                    ecx = 0x6c65746e; // "ntel"
                } else if (leaf == 1) {
                    eax = 0x00000663;
                    // FPU, TSC, MSR, CX8, SEP, CMOV, CLFSH, MMX, FXSR,
                    // SSE and SSE2.  These are safe baseline capability bits;
                    // AVX and later vector generations remain hidden.
                    edx = (1u<<0) | (1u<<4) | (1u<<5) | (1u<<8) |
                          (1u<<11) | (1u<<15) | (1u<<19) | (1u<<23) |
                          (1u<<24) | (1u<<25) | (1u<<26);
                    ecx = 0;
                } else if (leaf == 0x80000000u) {
                    eax = 0x80000001u;
                } else if (leaf == 0x80000001u) {
                    // SYSCALL/SYSRET, NX and long mode.  Do not advertise
                    // LAHF/SAHF here yet, since that belongs to x86-64-v2.
                    edx = (1u<<11) | (1u<<20) | (1u<<29);
                }
                write_reg_bits(cpu, X86_64_RAX, eax, 32);
                write_reg_bits(cpu, X86_64_RBX, ebx, 32);
                write_reg_bits(cpu, X86_64_RCX, ecx, 32);
                write_reg_bits(cpu, X86_64_RDX, edx, 32);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }
'''
if old not in s:
    raise SystemExit("CPUID block not found")
p.write_text(s.replace(old, new))
print("patched x86_64 CPUID with complete baseline/extended leaves")
