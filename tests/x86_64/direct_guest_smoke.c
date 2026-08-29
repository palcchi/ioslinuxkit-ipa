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

static struct cpu_state fresh_cpu(struct mmu *mmu) {
    struct cpu_state cpu = {0};
    cpu.mmu = mmu;
    cpu.pc = BASE;
    cpu.sp = BASE + sizeof(memory) - 16;
    return cpu;
}

static void test_exact_movups_sib(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x0f,0x10,0x64,0x16,0x08,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));

    const addr_t src = BASE + 0x300;
    for (unsigned i = 0; i < 16; i++)
        memory[(src - BASE) + i] = (uint8_t)(0xa0 + i);

    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RSI, BASE + 0x200);
    x86_64_set_reg(&cpu, X86_64_RDX, 0xf8);

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    fprintf(stderr,
            "[vmine-movups-result] interrupt=%d pc=%llx syscall=%llu xmm4=%02x%02x%02x%02x\n",
            interrupt, (unsigned long long)cpu.pc,
            (unsigned long long)cpu.x86_last_syscall,
            cpu.xmm[4].u8[0], cpu.xmm[4].u8[1], cpu.xmm[4].u8[2], cpu.xmm[4].u8[3]);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    for (unsigned i = 0; i < 16; i++)
        assert(cpu.xmm[4].u8[i] == (uint8_t)(0xa0 + i));
    puts("DIRECT X86_64 MOVUPS SIB: PASS");
}

static void test_exact_pminub(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0x66,0x0f,0xda,0x2f,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));

    const addr_t src = BASE + 0x300;
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RDI, src);
    for (unsigned i = 0; i < 16; i++) {
        cpu.xmm[5].u8[i] = (uint8_t)(0x80 + i);
        memory[(src - BASE) + i] = (i & 1) ? (uint8_t)(0xf0 + i) : (uint8_t)(0x10 + i);
    }

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    for (unsigned i = 0; i < 16; i++) {
        uint8_t expected = (i & 1) ? (uint8_t)(0x80 + i) : (uint8_t)(0x10 + i);
        assert(cpu.xmm[5].u8[i] == expected);
    }
    puts("DIRECT X86_64 PMINUB: PASS");
}

static void test_exact_imul_imm(void) {
    memset(memory, 0, sizeof(memory));

    const uint8_t program[] = {
        0x49,0x69,0xfc,0x03,0x00,0x00,0x00,
        0x4d,0x6b,0xfc,0xfe,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));

    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_R12, 7);

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RDI) == 21);
    assert(x86_64_get_reg(&cpu, X86_64_R15) == (uint64_t)-14);
    puts("DIRECT X86_64 IMUL IMM: PASS");
}

static void test_exact_xorps(void) {
    memset(memory, 0, sizeof(memory));

    const uint8_t program[] = {
        0x0f,0x57,0xc0,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));

    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.xmm[0].u128 = ~((__uint128_t)0);

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    assert(cpu.xmm[0].u128 == 0);
    puts("DIRECT X86_64 XORPS: PASS");
}

static void test_mov_r8_imm(void) {
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};

    // Exact BDS frontier: B0 01 = MOV AL, 1. Preserve the upper 56 bits.
    memset(memory, 0, sizeof(memory));
    const uint8_t al_program[] = {
        0xb0,0x01,
        0x48,0x89,0xc7,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, al_program, sizeof(al_program));
    struct cpu_state cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RAX, 0x1122334455667788ULL);
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    assert(x86_64_get_reg(&cpu, X86_64_RDI) == 0x1122334455667701ULL);

    // Legacy B4 means AH, not SPL.
    memset(memory, 0, sizeof(memory));
    const uint8_t ah_program[] = {
        0xb4,0xaa,
        0x48,0x89,0xc7,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, ah_program, sizeof(ah_program));
    cpu = fresh_cpu(&mmu);
    x86_64_set_reg(&cpu, X86_64_RAX, 0x1122334455667788ULL);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(x86_64_get_reg(&cpu, X86_64_RDI) == 0x112233445566aa88ULL);

    // With REX, B4 means SPL. REX.B on B0 reaches r8b.
    memset(memory, 0, sizeof(memory));
    const uint8_t rex_program[] = {
        0x40,0xb4,0x55,
        0x41,0xb0,0x5a,
        0x48,0x89,0xe7,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x0f,0x05,
    };
    memcpy(memory, rex_program, sizeof(rex_program));
    cpu = fresh_cpu(&mmu);
    uint64_t initial_sp = cpu.sp;
    x86_64_set_reg(&cpu, X86_64_R8, 0x8877665544332211ULL);
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(x86_64_get_reg(&cpu, X86_64_RDI) == ((initial_sp & ~0xffULL) | 0x55ULL));
    assert(x86_64_get_reg(&cpu, X86_64_R8) == 0x887766554433225aULL);

    puts("DIRECT X86_64 MOV R8 IMM: PASS");
}

static void test_write_exit(void) {
    memset(memory, 0, sizeof(memory));
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

    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 1);
    assert(cpu.regs[8] == 64);
    assert(cpu.regs[0] == 1);
    assert(cpu.regs[1] == BASE + 42);
    assert(cpu.regs[2] == 20);
    cpu.regs[0] = 20;
    interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    assert(cpu.regs[8] == 93);
    assert(cpu.regs[0] == 0);
    puts("DIRECT X86_64 GUEST INTERPRETER: PASS");
}

int main(void) {
    test_exact_movups_sib();
    test_exact_pminub();
    test_exact_imul_imm();
    test_exact_xorps();
    test_mov_r8_imm();
    test_write_exit();
    return 0;
}
