from pathlib import Path

p = Path("kernel/calls.c")
s = p.read_text()
old = '''            struct siginfo_ info = {
                .code = mem_segv_reason(current->mem, cpu->segfault_addr),
                .fault.addr = cpu->segfault_addr,
            };
'''
new = '''#ifdef GUEST_X86_64
            fprintf(stderr,
                    "[x86-gpf] pc=%llx fault=%llx write=%d fs=%llx rsp=%llx "
                    "rax=%llx rbx=%llx rcx=%llx rdx=%llx rsi=%llx rdi=%llx "
                    "r8=%llx r9=%llx r10=%llx r11=%llx\\n",
                    (unsigned long long)cpu->pc,
                    (unsigned long long)cpu->segfault_addr,
                    cpu->segfault_was_write ? 1 : 0,
                    (unsigned long long)cpu->tls_ptr,
                    (unsigned long long)cpu->sp,
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RAX),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RBX),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RCX),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RDX),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RSI),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_RDI),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_R8),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_R9),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_R10),
                    (unsigned long long)x86_64_get_reg(cpu, X86_64_R11));
            fprintf(stderr, "[x86-gpf-bytes]");
            for (int xi = -12; xi < 20; xi++) {
                uint8_t xb = 0;
                if (user_get(cpu->pc + xi, xb))
                    fprintf(stderr, " ??");
                else
                    fprintf(stderr, " %02x", xb);
            }
            fprintf(stderr, "\\n");
            dump_maps();
#endif
            struct siginfo_ info = {
                .code = mem_segv_reason(current->mem, cpu->segfault_addr),
                .fault.addr = cpu->segfault_addr,
            };
'''
if old not in s:
    raise SystemExit("GPF siginfo anchor not found")
p.write_text(s.replace(old, new, 1))
print("patched x86_64 GPF diagnostics with bytes/maps")
