#!/usr/bin/env python3
from pathlib import Path

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 66 0F 71/72/73 group: immediate packed integer shifts.
            // These include PSLLDQ/PSRLDQ, which glibc uses in baseline SSE2
            // routines while the dynamic loader is still starting up.
            if (operand16 && (op2 == 0x71 || op2 == 0x72 || op2 == 0x73)) {
                uint8_t modrm;
                if (fetch_u8(cpu, ip + 2, &modrm) < 0) goto gpf;
                unsigned raw_group = (modrm >> 3) & 7;
                bool supported =
                    (op2 == 0x71 && (raw_group == 2 || raw_group == 4 || raw_group == 6)) ||
                    (op2 == 0x72 && (raw_group == 2 || raw_group == 4 || raw_group == 6)) ||
                    (op2 == 0x73 && (raw_group == 2 || raw_group == 3 || raw_group == 6 || raw_group == 7));
                if (supported) {
                    struct rm_operand rm;
                    unsigned group;
                    addr_t next;
                    if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &group, &next) < 0) goto gpf;
                    if (!rm.is_reg || rm.reg >= 16) goto undefined;
                    uint8_t count;
                    if (fetch_u8(cpu, next - 1, &count) < 0) goto gpf;
                    union x86_64_xmm dst = cpu->xmm[rm.reg];

                    if (op2 == 0x71) {
                        if ((group & 7) == 2) {
                            for (unsigned i = 0; i < 8; i++)
                                dst.u16[i] = count >= 16 ? 0 : (uint16_t)(dst.u16[i] >> count);
                        } else if ((group & 7) == 4) {
                            unsigned c = count >= 16 ? 15 : count;
                            for (unsigned i = 0; i < 8; i++)
                                dst.u16[i] = (uint16_t)((int16_t)dst.u16[i] >> c);
                        } else {
                            for (unsigned i = 0; i < 8; i++)
                                dst.u16[i] = count >= 16 ? 0 : (uint16_t)(dst.u16[i] << count);
                        }
                    } else if (op2 == 0x72) {
                        if ((group & 7) == 2) {
                            for (unsigned i = 0; i < 4; i++)
                                dst.u32[i] = count >= 32 ? 0 : dst.u32[i] >> count;
                        } else if ((group & 7) == 4) {
                            unsigned c = count >= 32 ? 31 : count;
                            for (unsigned i = 0; i < 4; i++)
                                dst.u32[i] = (uint32_t)((int32_t)dst.u32[i] >> c);
                        } else {
                            for (unsigned i = 0; i < 4; i++)
                                dst.u32[i] = count >= 32 ? 0 : dst.u32[i] << count;
                        }
                    } else if ((group & 7) == 2) {
                        for (unsigned i = 0; i < 2; i++)
                            dst.u64[i] = count >= 64 ? 0 : dst.u64[i] >> count;
                    } else if ((group & 7) == 6) {
                        for (unsigned i = 0; i < 2; i++)
                            dst.u64[i] = count >= 64 ? 0 : dst.u64[i] << count;
                    } else if ((group & 7) == 3) {
                        // PSRLDQ: shift the whole 128-bit register right by bytes.
                        if (count >= 16) {
                            dst.u128 = 0;
                        } else if (count != 0) {
                            for (unsigned i = 0; i < 16 - count; i++)
                                dst.u8[i] = dst.u8[i + count];
                            for (unsigned i = 16 - count; i < 16; i++)
                                dst.u8[i] = 0;
                        }
                    } else {
                        // PSLLDQ: shift the whole 128-bit register left by bytes.
                        if (count >= 16) {
                            dst.u128 = 0;
                        } else if (count != 0) {
                            for (int i = 15; i >= (int)count; i--)
                                dst.u8[i] = dst.u8[i - count];
                            for (unsigned i = 0; i < count; i++)
                                dst.u8[i] = 0;
                        }
                    }
                    cpu->xmm[rm.reg] = dst;
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 interpreter with immediate SSE2 packed shifts")
