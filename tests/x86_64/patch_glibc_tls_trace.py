#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = """static int guest_write(struct cpu_state *cpu, addr_t addr, const void *value, size_t size) {
"""
insert = """static int guest_write(struct cpu_state *cpu, addr_t addr, const void *value, size_t size) {
#ifdef GUEST_X86_64
    static unsigned tls_write_traces;
    if (cpu->tls_ptr != 0 && addr >= cpu->tls_ptr && addr < cpu->tls_ptr + 0x100 &&
        tls_write_traces++ < 64) {
        uint64_t raw = 0;
        memcpy(&raw, value, size < sizeof(raw) ? size : sizeof(raw));
        fprintf(stderr,
                "[vmine-tls-write] pc=%llx fs=%llx addr=%llx size=%zu value=%llx\\n",
                (unsigned long long)cpu->pc,
                (unsigned long long)cpu->tls_ptr,
                (unsigned long long)addr, size,
                (unsigned long long)raw);
    }
#endif
"""
if anchor not in s:
    raise SystemExit("guest_write anchor missing")
path.write_text(s.replace(anchor, insert, 1))
print("patched targeted x86_64 TLS diagnostics")
