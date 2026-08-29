#!/usr/bin/env python3
from pathlib import Path

cpu = Path("emu/arch/x86_64/cpu.h")
s = cpu.read_text()
old = '''    uint32_t fpcr;
    uint32_t fpsr;

    uint64_t tls_ptr;
'''
new = '''    uint32_t fpcr;
    uint32_t fpsr;

    // Architectural x86 SSE control/status register. A freshly started x86_64
    // process observes MXCSR=0x1f80. Zero is used as our lazy-uninitialized
    // sentinel because Linux/glibc startup will establish a conventional value
    // before software intentionally asks for an all-zero MXCSR.
    uint32_t mxcsr;

    uint64_t tls_ptr;
'''
if old not in s:
    raise SystemExit("cpu floating-state anchor missing")
s = s.replace(old, new, 1)
cpu.write_text(s)

path = Path("emu/arch/x86_64/interp.c")
s = path.read_text()
anchor = '''            // SYSCALL.\n'''
insert = r'''            // 0F AE group: legacy FXSAVE/FXRSTOR, MXCSR load/store and
            // memory-order/cache hints. Jammy glibc reaches FXSAVE during its
            // startup/resolver path, so keep a coherent 512-byte legacy save
            // area rather than treating this merely as a feature-probe no-op.
            if (op2 == 0xae) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &group, &next) < 0) goto gpf;
                unsigned sub = group & 7;

                if (!rm.is_reg && sub == 0) { // FXSAVE m512
                    uint8_t area[512] = {0};
                    uint16_t fcw = 0x037f;
                    uint16_t fsw = 0;
                    uint8_t ftw = 0;
                    uint32_t mxcsr = cpu->mxcsr ? cpu->mxcsr : 0x1f80u;
                    uint32_t mxcsr_mask = 0x0000ffbfu;
                    memcpy(area + 0, &fcw, sizeof(fcw));
                    memcpy(area + 2, &fsw, sizeof(fsw));
                    memcpy(area + 4, &ftw, sizeof(ftw));
                    memcpy(area + 24, &mxcsr, sizeof(mxcsr));
                    memcpy(area + 28, &mxcsr_mask, sizeof(mxcsr_mask));

                    // The x87/MM slots occupy 8 x 16 bytes beginning at 32.
                    // cpu->fp is represented as 128-bit slots during bring-up;
                    // preserving the first eight gives FXRSTOR a stable roundtrip.
                    for (unsigned i = 0; i < 8; i++)
                        memcpy(area + 32 + i * 16, &cpu->fp[i], 16);

                    // In 64-bit mode the legacy FXSAVE region contains XMM0..15
                    // in sixteen consecutive 16-byte slots beginning at 160.
                    for (unsigned i = 0; i < 16; i++)
                        memcpy(area + 160 + i * 16, &cpu->xmm[i], 16);

                    if (guest_write(cpu, rm.addr, area, sizeof(area)) < 0) goto gpf;
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }

                if (!rm.is_reg && sub == 1) { // FXRSTOR m512
                    uint8_t area[512];
                    if (guest_read(cpu, rm.addr, area, sizeof(area)) < 0) goto gpf;
                    uint32_t mxcsr;
                    memcpy(&mxcsr, area + 24, sizeof(mxcsr));
                    // Ignore unsupported/reserved MXCSR bits just as our
                    // conservative virtual CPU hides unsupported SIMD features.
                    cpu->mxcsr = mxcsr & 0x0000ffbfu;
                    for (unsigned i = 0; i < 8; i++)
                        memcpy(&cpu->fp[i], area + 32 + i * 16, 16);
                    for (unsigned i = 0; i < 16; i++)
                        memcpy(&cpu->xmm[i], area + 160 + i * 16, 16);
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }

                if (!rm.is_reg && sub == 2) { // LDMXCSR m32
                    uint32_t value;
                    if (guest_read(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                    if (value & ~0x0000ffbfu) goto gpf;
                    cpu->mxcsr = value;
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }

                if (!rm.is_reg && sub == 3) { // STMXCSR m32
                    uint32_t value = cpu->mxcsr ? cpu->mxcsr : 0x1f80u;
                    if (guest_write(cpu, rm.addr, &value, sizeof(value)) < 0) goto gpf;
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }

                // LFENCE/MFENCE/SFENCE have no extra action in this direct,
                // in-order interpreter. CLFLUSH/CLFLUSHOPT-style memory forms
                // likewise do not need a host cache operation because guest
                // memory is already coherent from the interpreter's viewpoint.
                if ((rm.is_reg && (sub == 5 || sub == 6 || sub == 7)) ||
                    (!rm.is_reg && sub == 7)) {
                    cpu->pc = next;
                    cpu->cycle++;
                    continue;
                }

                goto undefined;
            }

'''
if anchor not in s:
    raise SystemExit("0F dispatch syscall anchor missing")
s = s.replace(anchor, insert + anchor, 1)
path.write_text(s)
print("patched x86_64 FXSAVE/FXRSTOR/MXCSR and 0F AE fence group")
