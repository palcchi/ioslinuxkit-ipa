#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 10/11 and 0F 28/29: MOVUPS/MOVAPS. The 66-prefixed
            // forms (MOVUPD/MOVAPD) have identical 128-bit copy semantics here.
            // Alignment faults are intentionally deferred during loader bring-up.
            if (op2 == 0x10 || op2 == 0x11 || op2 == 0x28 || op2 == 0x29) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (op2 == 0x10) {
                    fprintf(stderr,
                            "[vmine-0f10-decoded] xmm=%u isreg=%d rmreg=%u addr=%llx next=%llx\n",
                            xmm, rm.is_reg ? 1 : 0, rm.reg,
                            (unsigned long long)rm.addr,
                            (unsigned long long)next);
                }
                if (xmm >= 16) goto undefined;
                bool load = (op2 == 0x10 || op2 == 0x28);
                if (load) {
                    union x86_64_xmm value;
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        value = cpu->xmm[rm.reg];
                    } else if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) {
                        goto gpf;
                    }
                    cpu->xmm[xmm] = value;
                } else {
                    union x86_64_xmm value = cpu->xmm[xmm];
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        cpu->xmm[rm.reg] = value;
                    } else if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) {
                        goto gpf;
                    }
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
print("patched x86_64 interpreter with SSE packed moves")
