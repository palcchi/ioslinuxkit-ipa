#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F C6 /r ib: SHUFPS. 66 0F C6 /r ib: SHUFPD.
            // glibc uses these during early CPU-feature/vector setup.
            if (op2 == 0xc6 && !rep_prefix) {
                struct rm_operand rm;
                unsigned xmm;
                addr_t next;
                union x86_64_xmm src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &xmm, &next) < 0) goto gpf;
                if (xmm >= 16) goto undefined;
                if (rm.is_reg) {
                    if (rm.reg >= 16) goto undefined;
                    src = cpu->xmm[rm.reg];
                } else if (guest_read(cpu, rm.addr, &src, sizeof(src)) < 0) {
                    goto gpf;
                }
                uint8_t imm;
                if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                union x86_64_xmm old = cpu->xmm[xmm];
                union x86_64_xmm out = old;
                if (operand16) {
                    // SHUFPD: low qword selected from old dest, high qword
                    // selected from source. Only imm bits 0 and 1 matter.
                    out.u64[0] = old.u64[(imm >> 0) & 1];
                    out.u64[1] = src.u64[(imm >> 1) & 1];
                } else {
                    // SHUFPS: first two dwords come from old dest, final two
                    // from source, each selected by its 2-bit immediate field.
                    out.u32[0] = old.u32[(imm >> 0) & 3];
                    out.u32[1] = old.u32[(imm >> 2) & 3];
                    out.u32[2] = src.u32[(imm >> 4) & 3];
                    out.u32[3] = src.u32[(imm >> 6) & 3];
                }
                cpu->xmm[xmm] = out;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with SHUFPS/SHUFPD")
