#ifndef EMU_CPU_H
#define EMU_CPU_H

#include "misc.h"
#include "emu/mmu.h"

#ifdef __KERNEL__
#include <linux/stddef.h>
#else
#include <stddef.h>
#endif

// Guest CPU state is selected at compile time. ARM64 remains the production
// backend; x86_64 is an experimental direct interpreter bring-up target.
#if defined(GUEST_ARM64) && defined(GUEST_X86_64)
#error "Select exactly one guest architecture"
#elif defined(GUEST_ARM64)
#include "emu/arch/arm64/cpu.h"
#elif defined(GUEST_X86_64)
#include "emu/arch/x86_64/cpu.h"
#else
#error "No guest architecture selected"
#endif

// Common CPU interface
struct cpu_state;
struct tlb;
int cpu_run_to_interrupt(struct cpu_state *cpu, struct tlb *tlb);
void cpu_poke(struct cpu_state *cpu);

#ifndef CPU_OFFSET
#define CPU_OFFSET(field) offsetof(struct cpu_state, field)
#endif

#endif
