#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "emu/cpu.h"
#include "emu/interrupt.h"
#include "emu/mmu.h"

#define BASE 0x1000ULL

static uint8_t memory[4096];

static void *test_translate(struct mmu *mmu, addr_t addr, int type) {
    (void) mmu;
    (void) type;
    if (addr < BASE || addr >= BASE + sizeof(memory))
        return NULL;
    return &memory[addr - BASE];
}

static void *test_translate_write_nofault(struct mmu *mmu, addr_t addr) {
    return test_translate(mmu, addr, MEM_WRITE);
}

static struct mmu_ops ops = {
    .translate = test_translate,
    .translate_write_nofault = test_translate_write_nofault,
};

int main(void) {
    // Linux x86_64 machine code:
    //   mov $1,%rax              ; write
    //   mov $1,%rdi              ; stdout
    //   lea msg(%rip),%rsi
    //   mov $20,%rdx
    //   syscall
    //   mov $60,%rax             ; exit
    //   xor %rdi,%rdi
    //   syscall
    // msg: "DIRECT X86_64 GUEST\n"
    const uint8_t program[] = {
        0x48,0xc7,0xc0,0x01,0x00,0x00,0x00,
        0x48,0xc7,0xc7,0x01,0x00,0x00,0x00,
        0x48,0x8d,0x35,0x15,0x00,0x00,0x00,
        0x48,0xc7,0xc2,0x14,0x00,0x00,0x00,
        0x0f,0x05,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
        'D','I','R','E','C','T',' ','X','8','6','_','6','4',' ','G','U','E','S','T','\n'
    };
    memcpy(memory, program, sizeof(program));

    struct mmu mmu = {
        .ops = &ops,
        .asbestos = NULL,
        .changes = 0,
    };
    struct cpu_state cpu = {0};
    cpu.mmu = &mmu;
    cpu.pc = BASE;
    cpu.sp = BASE + sizeof(memory) - 16;

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 1);   // x86_64 write
    assert(cpu.regs[8] == 64);           // compatibility AArch64 write
    assert(cpu.regs[0] == 1);            // fd
    assert(cpu.regs[1] == BASE + 42);    // message address
    assert(cpu.regs[2] == 20);           // message length

    // Simulate the shared kernel returning write() = 20 in compatibility x0.
    cpu.regs[0] = 20;

    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);  // x86_64 exit
    assert(cpu.regs[8] == 93);           // compatibility AArch64 exit
    assert(cpu.regs[0] == 0);            // status

    puts("DIRECT X86_64 GUEST INTERPRETER: PASS");
    return 0;
}
