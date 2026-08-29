#ifndef EMU_ARCH_X86_64_CPU_H
#define EMU_ARCH_X86_64_CPU_H

#include "misc.h"
#include "emu/mmu.h"

#ifdef __KERNEL__
#include <linux/stddef.h>
#else
#include <stddef.h>
#endif

// Architectural register numbering follows the low three ModRM register bits,
// extended by REX.R/REX.B. RSP is kept in cpu->sp so existing 64-bit kernel
// exec code can initialize the stack without an architecture-specific fork.
enum x86_64_reg {
    X86_64_RAX = 0,
    X86_64_RCX = 1,
    X86_64_RDX = 2,
    X86_64_RBX = 3,
    X86_64_RSP = 4,
    X86_64_RBP = 5,
    X86_64_RSI = 6,
    X86_64_RDI = 7,
    X86_64_R8  = 8,
    X86_64_R9  = 9,
    X86_64_R10 = 10,
    X86_64_R11 = 11,
    X86_64_R12 = 12,
    X86_64_R13 = 13,
    X86_64_R14 = 14,
    X86_64_R15 = 15,
};

union x86_64_xmm {
    __uint128_t u128;
    uint64_t u64[2];
    uint32_t u32[4];
    uint16_t u16[8];
    uint8_t u8[16];
    float f32[4];
    double f64[2];
};

struct cpu_state {
    struct mmu *mmu;
    long cycle;

    // Native x86_64 architectural GPRs. RSP lives in sp below.
    uint64_t x86_regs[16];
    uint64_t sp;

    union {
        uint64_t rip;
        uint64_t pc;
    };

    uint64_t rflags;

    // Canonical flag bytes. Keeping these named fields also lets shared kernel
    // diagnostics compile while the x86_64 signal ABI is brought up.
    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t vf;
    uint32_t nzcv;

    union x86_64_xmm xmm[16];
    // Compatibility storage used by shared ARM64-oriented save paths during
    // early bring-up. It is not the final x86_64 FP ABI representation.
    union x86_64_xmm fp[32];
    uint32_t fpcr;
    uint32_t fpsr;

    uint64_t tls_ptr;

    addr_t segfault_addr;
    bool segfault_was_write;
    dword_t trapno;

    bool *poked_ptr;
    bool _poked;

    // Shared-kernel syscall compatibility view. The direct interpreter maps
    // Linux x86_64 syscall registers/numbers into this view before returning
    // INT_SYSCALL. This keeps the existing userspace-kernel syscall handlers
    // reusable while x86_64-specific tables and structures are implemented.
    uint64_t regs[16];
    bool x86_syscall_pending;
    uint64_t x86_last_syscall;
};

static inline uint64_t x86_64_get_reg(const struct cpu_state *cpu, unsigned reg) {
    if (reg == X86_64_RSP)
        return cpu->sp;
    return cpu->x86_regs[reg & 15];
}

static inline void x86_64_set_reg(struct cpu_state *cpu, unsigned reg, uint64_t value) {
    if (reg == X86_64_RSP)
        cpu->sp = value;
    else
        cpu->x86_regs[reg & 15] = value;
}

static inline uint64_t x86_64_get_rax(const struct cpu_state *cpu) {
    return x86_64_get_reg(cpu, X86_64_RAX);
}

static inline void x86_64_set_rax(struct cpu_state *cpu, uint64_t value) {
    x86_64_set_reg(cpu, X86_64_RAX, value);
}

static inline void collapse_flags(struct cpu_state *cpu) {
    uint64_t f = cpu->rflags | 0x2;
    if (cpu->cf) f |= 1ULL << 0; else f &= ~(1ULL << 0);
    if (cpu->zf) f |= 1ULL << 6; else f &= ~(1ULL << 6);
    if (cpu->nf) f |= 1ULL << 7; else f &= ~(1ULL << 7);
    if (cpu->vf) f |= 1ULL << 11; else f &= ~(1ULL << 11);
    cpu->rflags = f;
}

static inline void expand_flags(struct cpu_state *cpu) {
    cpu->cf = (cpu->rflags >> 0) & 1;
    cpu->zf = (cpu->rflags >> 6) & 1;
    cpu->nf = (cpu->rflags >> 7) & 1;
    cpu->vf = (cpu->rflags >> 11) & 1;
}

static_assert(sizeof(union x86_64_xmm) == 16, "x86_64_xmm size");

#endif
