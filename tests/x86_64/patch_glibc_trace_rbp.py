from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
anchor = '''        addr_t insn_start = cpu->pc;
        addr_t ip = insn_start;
'''
insert = '''        addr_t insn_start = cpu->pc;

        // Temporary bring-up diagnostic: identify the exact instruction that
        // changes a stack-like RBP value. The Jammy loader currently arrives
        // at a relocation-frame load with RBP shifted by 0xb0, so logging the
        // transition here is much more useful than another post-crash dump.
        static uint64_t trace_last_rbp;
        static addr_t trace_prev_pc;
        uint64_t trace_rbp = x86_64_get_reg(cpu, X86_64_RBP);
        if (trace_last_rbp != 0 && trace_rbp != trace_last_rbp &&
            trace_last_rbp >= 0xff000000ULL && trace_rbp >= 0xff000000ULL) {
            uint8_t tb[12] = {0};
            size_t tn = 0;
            for (; tn < sizeof(tb); tn++) {
                if (guest_read(cpu, trace_prev_pc + tn, &tb[tn], 1) < 0)
                    break;
            }
            fprintf(stderr,
                    "[x86-rbp-change] prevpc=%llx nextpc=%llx old=%llx new=%llx bytes=",
                    (unsigned long long)trace_prev_pc,
                    (unsigned long long)insn_start,
                    (unsigned long long)trace_last_rbp,
                    (unsigned long long)trace_rbp);
            for (size_t ti = 0; ti < tn; ti++) fprintf(stderr, "%02x", tb[ti]);
            fprintf(stderr, "\\n");
        }
        trace_last_rbp = trace_rbp;
        trace_prev_pc = insn_start;

        addr_t ip = insn_start;
'''
if anchor not in s:
    raise SystemExit("instruction-loop anchor not found")
p.write_text(s.replace(anchor, insert, 1))
print("patched x86_64 interpreter with exact RBP transition trace")
