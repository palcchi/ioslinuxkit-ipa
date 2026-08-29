#!/usr/bin/env python3
from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
if '#include <stdio.h>\n' not in s:
    inc = '#include <string.h>\n'
    if inc not in s:
        raise SystemExit('include anchor missing')
    s = s.replace(inc, inc + '#include <stdio.h>\n', 1)

# The failing POP RBX consumes ffffdd28 in the normal exec path and ffffdd18
# in the explicit-loader path. Record every write overlapping either slot so
# we can distinguish a legitimate saved-register push from later corruption.
write_anchor = '''    return 0;\n}\n\nstatic int fetch_u8'''
write_insert = r'''    const addr_t vmine_slots[] = {0xffffdd18ULL, 0xffffdd28ULL};
    for (unsigned si = 0; si < sizeof(vmine_slots) / sizeof(vmine_slots[0]); si++) {
        addr_t slot = vmine_slots[si];
        if (addr < slot + 8 && addr + size > slot) {
            uint64_t observed = 0;
            bool mapped = true;
            for (unsigned j = 0; j < 8; j++) {
                uint8_t *b = mmu_translate(cpu->mmu, slot + j, MEM_READ);
                if (b == NULL) {
                    mapped = false;
                    break;
                }
                observed |= (uint64_t)(*b) << (j * 8);
            }
            fprintf(stderr,
                    "[vmine-rbx-slot-write] pc=%llx write_addr=%llx size=%llu slot=%llx value=%s%llx rsp=%llx bytes=",
                    (unsigned long long)cpu->pc,
                    (unsigned long long)addr,
                    (unsigned long long)size,
                    (unsigned long long)slot,
                    mapped ? "" : "unmapped:",
                    (unsigned long long)observed,
                    (unsigned long long)cpu->sp);
            for (unsigned xi = 0; xi < 16; xi++) {
                uint8_t *xb = mmu_translate(cpu->mmu, cpu->pc + xi, MEM_READ);
                if (xb == NULL) fprintf(stderr, "??");
                else fprintf(stderr, "%02x", *xb);
            }
            fprintf(stderr, "\n");
        }
    }
    return 0;
}

static int fetch_u8'''
if write_anchor not in s:
    raise SystemExit('guest_write return anchor missing')
s = s.replace(write_anchor, write_insert, 1)

anchor = '''    for (unsigned step = 0; step < INTERP_SLICE; step++) {\n'''
insert = r'''    // Temporary BDS bring-up diagnostic. Capture when RBX first acquires the
    // impossible 0x77 high dword and show the instructions around the POP that
    // restores it from the stack.
    static bool vmine_rbx_init = false;
    static bool vmine_rbx_origin_seen = false;
    static uint64_t vmine_prev_rbx = 0;
    static addr_t vmine_prev_pc = 0;

'''
if anchor not in s:
    raise SystemExit('interpreter loop anchor missing')
s = s.replace(anchor, insert + anchor, 1)

loop_anchor = '''        if (__atomic_exchange_n(cpu->poked_ptr, false, __ATOMIC_SEQ_CST)) {\n'''
loop_insert = r'''        uint64_t vmine_cur_rbx = x86_64_get_reg(cpu, X86_64_RBX);
        bool vmine_rbx_bad_high = (vmine_cur_rbx >> 32) == 0x77ULL;
        bool vmine_prev_bad_high = (vmine_prev_rbx >> 32) == 0x77ULL;
        if (vmine_rbx_init && !vmine_rbx_origin_seen && vmine_rbx_bad_high &&
            !vmine_prev_bad_high) {
            fprintf(stderr,
                    "[vmine-rbx-origin] prevpc=%llx nextpc=%llx old=%llx new=%llx rsp=%llx around=",
                    (unsigned long long)vmine_prev_pc,
                    (unsigned long long)cpu->pc,
                    (unsigned long long)vmine_prev_rbx,
                    (unsigned long long)vmine_cur_rbx,
                    (unsigned long long)cpu->sp);
            addr_t start = vmine_prev_pc >= 32 ? vmine_prev_pc - 32 : 0;
            for (unsigned xi = 0; xi < 48; xi++) {
                uint8_t xb = 0;
                if (guest_read(cpu, start + xi, &xb, 1) < 0)
                    fprintf(stderr, "??");
                else
                    fprintf(stderr, "%02x", xb);
            }
            fprintf(stderr, "\n");
            vmine_rbx_origin_seen = true;
        }
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
print('patched targeted saved-RBX slot trace')
