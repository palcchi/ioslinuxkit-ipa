#ifndef EMU_ARCH_X86_64_CPU_H
#define EMU_ARCH_X86_64_CPU_H

#include "misc.h"
#include "emu/mmu.h"

#ifdef __KERNEL__
#include <linux/stddef.h>
#else
#include <stddef.h>
#endif

enum x86_64_reg {
    X86_64_RAX = 0, X86_64_RCX = 1, X86_64_RDX = 2, X86_64_RBX = 3,
    X86_64_RSP = 4, X86_64_RBP = 5, X86_64_RSI = 6, X86_64_RDI = 7,
    X86_64_R8 = 8, X86_64_R9 = 9, X86_64_R10 = 10, X86_64_R11 = 11,
    X86_64_R12 = 12, X86_64_R13 = 13, X86_64_R14 = 14, X86_64_R15 = 15,
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

    // Native x86_64 architectural GPRs. The e* aliases are deliberately kept
    // 64-bit during bring-up so legacy shared-kernel paths cannot truncate
    // actual x86_64 pointers while we replace the old i386 ABI code.
    union {
        uint64_t x86_regs[16];
        struct {
            union { uint64_t rax; uint64_t eax; };
            union { uint64_t rcx; uint64_t ecx; };
            union { uint64_t rdx; uint64_t edx; };
            union { uint64_t rbx; uint64_t ebx; };
            uint64_t rsp_slot;
            union { uint64_t rbp; uint64_t ebp; };
            union { uint64_t rsi; uint64_t esi; };
            union { uint64_t rdi; uint64_t edi; };
            uint64_t r8, r9, r10, r11, r12, r13, r14, r15;
        };
    };

    union { uint64_t sp; uint64_t esp; };
    union { uint64_t rip; uint64_t pc; uint64_t eip; };
    union { uint64_t rflags; uint64_t eflags; };

    uint8_t nf;
    uint8_t zf;
    uint8_t cf;
    uint8_t vf;
    // Temporary single-step compatibility for ptrace. Eventually this becomes
    // architectural RFLAGS.TF handling in the x86_64 interpreter itself.
    bool tf;
    uint32_t nzcv;

    union x86_64_xmm xmm[16];
    union x86_64_xmm fp[32];
    uint32_t fpcr;
    uint32_t fpsr;

    uint64_t tls_ptr;

    addr_t segfault_addr;
    bool segfault_was_write;
    dword_t trapno;

    bool *poked_ptr;
    bool _poked;

    // Shared-kernel syscall compatibility view. Architectural x86_64 state is
    // kept separately in x86_regs.
    uint64_t regs[32];
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
    if (cpu->tf) f |= 1ULL << 8; else f &= ~(1ULL << 8);
    if (cpu->vf) f |= 1ULL << 11; else f &= ~(1ULL << 11);
    cpu->rflags = f;
}

static inline void expand_flags(struct cpu_state *cpu) {
    cpu->cf = (cpu->rflags >> 0) & 1;
    cpu->zf = (cpu->rflags >> 6) & 1;
    cpu->nf = (cpu->rflags >> 7) & 1;
    cpu->tf = (cpu->rflags >> 8) & 1;
    cpu->vf = (cpu->rflags >> 11) & 1;
}

static_assert(sizeof(union x86_64_xmm) == 16, "x86_64_xmm size");

#endif
