#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
if '#include <stdio.h>\n' not in s:
    inc = '#include <string.h>\n'
    if inc not in s:
        raise SystemExit('include anchor missing')
    s = s.replace(inc, inc + '#include <stdio.h>\n', 1)

anchor = '''    for (unsigned step = 0; step < INTERP_SLICE; step++) {\n'''
insert = r'''    // Temporary BDS bring-up diagnostic for the exact corrupted loop index
    // observed at the indirect-call frontier. This is diagnostic only, never
    // a behavioral workaround.
    static bool vmine_rbx_init = false;
    static uint64_t vmine_prev_rbx = 0;
    static addr_t vmine_prev_pc = 0;

'''
if anchor not in s:
    raise SystemExit('interpreter loop anchor missing')
s = s.replace(anchor, insert + anchor, 1)

loop_anchor = '''        if (__atomic_exchange_n(cpu->poked_ptr, false, __ATOMIC_SEQ_CST)) {\n'''
loop_insert = r'''        uint64_t vmine_cur_rbx = x86_64_get_reg(cpu, X86_64_RBX);
        if (vmine_rbx_init && vmine_cur_rbx == 0x770000007dULL &&
            vmine_cur_rbx != vmine_prev_rbx) {
            fprintf(stderr,
                    "[vmine-rbx-target] prevpc=%llx nextpc=%llx old=%llx new=%llx bytes=",
                    (unsigned long long)vmine_prev_pc,
                    (unsigned long long)cpu->pc,
                    (unsigned long long)vmine_prev_rbx,
                    (unsigned long long)vmine_cur_rbx);
            for (unsigned xi = 0; xi < 16; xi++) {
                uint8_t xb = 0;
                if (guest_read(cpu, vmine_prev_pc + xi, &xb, 1) < 0)
                    fprintf(stderr, "??");
                else
                    fprintf(stderr, "%02x", xb);
            }
            fprintf(stderr, "\n");
        }
        vmine_prev_rbx = vmine_cur_rbx;
        vmine_prev_pc = cpu->pc;
        vmine_rbx_init = true;

'''
if loop_anchor not in s:
    raise SystemExit('loop body anchor missing')
s = s.replace(loop_anchor, loop_insert + loop_anchor, 1)
p.write_text(s)
print('patched targeted RBX corruption trace')
