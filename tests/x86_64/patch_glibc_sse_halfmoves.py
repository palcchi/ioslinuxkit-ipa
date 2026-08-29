#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F 12/13/16/17: MOVLPS/MOVHPS plus the register-only
            // MOVHLPS/MOVLHPS forms. The 66-prefixed MOVLPD/MOVHPD memory
            // forms share the same bit-copy behavior for our purposes.
            if (op2 == 0x12 || op2 == 0x13 || op2 == 0x16 || op2 == 0x17) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;

                if (op2 == 0x12) {
                    // MOVLPS xmm,m64 or MOVHLPS xmm,xmm.
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        cpu->xmm[xmm].u64[0] = cpu->xmm[rm.reg].u64[1];
                    } else {
                        uint64_t value;
                        if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                        cpu->xmm[xmm].u64[0] = value;
                    }
                } else if (op2 == 0x16) {
                    // MOVHPS xmm,m64 or MOVLHPS xmm,xmm.
                    if (rm.is_reg) {
                        if (rm.reg >= 16) goto undefined;
                        cpu->xmm[xmm].u64[1] = cpu->xmm[rm.reg].u64[0];
                    } else {
                        uint64_t value;
                        if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                        cpu->xmm[xmm].u64[1] = value;
                    }
                } else {
                    // MOVLPS/MOVHPS stores require a memory operand.
                    if (rm.is_reg) goto undefined;
                    uint64_t value = cpu->xmm[xmm].u64[op2 == 0x17 ? 1 : 0];
                    if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
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
print("patched x86_64 interpreter with SSE half-register moves")
