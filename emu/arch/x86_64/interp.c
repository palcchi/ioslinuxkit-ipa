#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "emu/cpu.h"
#include "emu/interrupt.h"
#include "emu/mmu.h"

// Direct, non-JIT x86_64 bring-up interpreter. This deliberately starts tiny:
// enough instructions to execute a hand-written Linux syscall smoke program.
// It runs x86_64 guest instructions directly against LinuxKit's MMU and does
// not invoke qemu-x86_64 inside the ARM64 guest.

#define X86_64_ENOSYS 38
#define INTERP_SLICE 100000

static int guest_read(struct cpu_state *cpu, addr_t addr, void *out, size_t size) {
    uint8_t *dst = out;
    for (size_t i = 0; i < size; i++) {
        uint8_t *src = mmu_translate(cpu->mmu, addr + i, MEM_READ);
        if (src == NULL) {
            cpu->segfault_addr = addr + i;
            cpu->segfault_was_write = false;
            return -1;
        }
        dst[i] = *src;
    }
    return 0;
}

static int fetch_u8(struct cpu_state *cpu, addr_t addr, uint8_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static int fetch_u32(struct cpu_state *cpu, addr_t addr, uint32_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static int fetch_u64(struct cpu_state *cpu, addr_t addr, uint64_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static void set_logic_flags(struct cpu_state *cpu, uint64_t value, unsigned bits) {
    uint64_t mask = bits == 32 ? UINT32_MAX : UINT64_MAX;
    uint64_t v = value & mask;
    cpu->zf = v == 0;
    cpu->nf = (v >> (bits - 1)) & 1;
    cpu->cf = 0;
    cpu->vf = 0;
}

// Early syscall bridge: x86_64 Linux numbers -> the existing AArch64 syscall
// table numbers. Arguments are copied separately, so only number translation
// is needed for simple ABI-compatible syscalls. Complex structure/layout cases
// will move to a native x86_64 syscall table later.
static int x86_64_to_compat_syscall(uint64_t nr) {
    switch (nr) {
        case 0:   return 63;   // read
        case 1:   return 64;   // write
        case 3:   return 57;   // close
        case 8:   return 62;   // lseek
        case 9:   return 222;  // mmap
        case 10:  return 226;  // mprotect
        case 11:  return 215;  // munmap
        case 12:  return 214;  // brk
        case 13:  return 134;  // rt_sigaction
        case 14:  return 135;  // rt_sigprocmask
        case 15:  return 139;  // rt_sigreturn
        case 16:  return 29;   // ioctl
        case 17:  return 67;   // pread64
        case 18:  return 68;   // pwrite64
        case 19:  return 65;   // readv
        case 20:  return 66;   // writev
        case 24:  return 124;  // sched_yield
        case 25:  return 216;  // mremap
        case 26:  return 227;  // msync
        case 28:  return 233;  // madvise
        case 32:  return 23;   // dup
        case 35:  return 101;  // nanosleep
        case 39:  return 172;  // getpid
        case 41:  return 198;  // socket
        case 42:  return 203;  // connect
        case 43:  return 202;  // accept
        case 44:  return 206;  // sendto
        case 45:  return 207;  // recvfrom
        case 46:  return 211;  // sendmsg
        case 47:  return 212;  // recvmsg
        case 48:  return 210;  // shutdown
        case 49:  return 200;  // bind
        case 50:  return 201;  // listen
        case 51:  return 204;  // getsockname
        case 52:  return 205;  // getpeername
        case 53:  return 199;  // socketpair
        case 54:  return 208;  // setsockopt
        case 55:  return 209;  // getsockopt
        case 56:  return 220;  // clone
        case 59:  return 221;  // execve
        case 60:  return 93;   // exit
        case 61:  return 260;  // wait4
        case 62:  return 129;  // kill
        case 63:  return 160;  // uname
        case 72:  return 25;   // fcntl
        case 74:  return 82;   // fsync
        case 79:  return 17;   // getcwd
        case 80:  return 49;   // chdir
        case 96:  return 169;  // gettimeofday
        case 102: return 174;  // getuid
        case 104: return 176;  // getgid
        case 107: return 175;  // geteuid
        case 108: return 177;  // getegid
        case 110: return 173;  // getppid
        case 112: return 157;  // setsid
        case 186: return 178;  // gettid
        case 202: return 98;   // futex
        case 217: return 61;   // getdents64
        case 218: return 96;   // set_tid_address
        case 228: return 113;  // clock_gettime
        case 231: return 94;   // exit_group
        case 233: return 21;   // epoll_ctl
        case 234: return 131;  // tgkill
        case 257: return 56;   // openat
        case 262: return 79;   // newfstatat
        case 263: return 35;   // unlinkat
        case 267: return 78;   // readlinkat
        case 271: return 73;   // ppoll
        case 273: return 99;   // set_robust_list
        case 274: return 100;  // get_robust_list
        case 281: return 22;   // epoll_pwait
        case 290: return 19;   // eventfd2
        case 292: return 24;   // dup3
        case 293: return 59;   // pipe2
        case 302: return 261;  // prlimit64
        case 318: return 278;  // getrandom
        case 319: return 279;  // memfd_create
        case 332: return 291;  // statx
        case 334: return 293;  // rseq
        case 435: return 435;  // clone3
        case 436: return 436;  // close_range
        case 437: return 437;  // openat2
        default:  return -1;
    }
}

static void bridge_syscall(struct cpu_state *cpu, uint64_t guest_nr, int compat_nr) {
    cpu->x86_last_syscall = guest_nr;
    cpu->regs[8] = (uint64_t) compat_nr;
    cpu->regs[0] = x86_64_get_reg(cpu, X86_64_RDI);
    cpu->regs[1] = x86_64_get_reg(cpu, X86_64_RSI);
    cpu->regs[2] = x86_64_get_reg(cpu, X86_64_RDX);
    cpu->regs[3] = x86_64_get_reg(cpu, X86_64_R10);
    cpu->regs[4] = x86_64_get_reg(cpu, X86_64_R8);
    cpu->regs[5] = x86_64_get_reg(cpu, X86_64_R9);
    cpu->x86_syscall_pending = true;
}

static int decode_reg_reg(struct cpu_state *cpu, uint8_t rex, uint8_t modrm,
                          unsigned *reg, unsigned *rm) {
    unsigned mod = modrm >> 6;
    if (mod != 3)
        return -1;
    *reg = ((modrm >> 3) & 7) | ((rex & 0x4) ? 8 : 0);
    *rm = (modrm & 7) | ((rex & 0x1) ? 8 : 0);
    return 0;
}

int cpu_run_to_interrupt(struct cpu_state *cpu, struct tlb *tlb) {
    (void) tlb;

    if (cpu->poked_ptr == NULL)
        cpu->poked_ptr = &cpu->_poked;

    // The shared syscall dispatcher writes the return value into compatibility
    // regs[0]. Commit it to architectural RAX before executing the next x86_64
    // instruction.
    if (cpu->x86_syscall_pending) {
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }

    for (unsigned step = 0; step < INTERP_SLICE; step++) {
        if (__atomic_exchange_n(cpu->poked_ptr, false, __ATOMIC_SEQ_CST)) {
            cpu->trapno = INT_TIMER;
            return INT_TIMER;
        }

        addr_t ip = cpu->pc;
        uint8_t op;
        if (fetch_u8(cpu, ip, &op) < 0) {
            cpu->trapno = INT_GPF;
            return INT_GPF;
        }

        // ENDBR64, treated as a no-op while CET itself is not exposed.
        if (op == 0xf3) {
            uint8_t b1, b2, b3;
            if (fetch_u8(cpu, ip + 1, &b1) == 0 &&
                fetch_u8(cpu, ip + 2, &b2) == 0 &&
                fetch_u8(cpu, ip + 3, &b3) == 0 &&
                b1 == 0x0f && b2 == 0x1e && b3 == 0xfa) {
                cpu->pc += 4;
                cpu->cycle++;
                continue;
            }
        }

        uint8_t rex = 0;
        if (op >= 0x40 && op <= 0x4f) {
            rex = op;
            ip++;
            if (fetch_u8(cpu, ip, &op) < 0) {
                cpu->trapno = INT_GPF;
                return INT_GPF;
            }
        }

        // MOV r64, imm64 / MOV r32, imm32
        if (op >= 0xb8 && op <= 0xbf) {
            unsigned reg = (op - 0xb8) | ((rex & 0x1) ? 8 : 0);
            if (rex & 0x8) {
                uint64_t imm;
                if (fetch_u64(cpu, ip + 1, &imm) < 0) goto gpf;
                x86_64_set_reg(cpu, reg, imm);
                cpu->pc = ip + 9;
            } else {
                uint32_t imm;
                if (fetch_u32(cpu, ip + 1, &imm) < 0) goto gpf;
                x86_64_set_reg(cpu, reg, imm);
                cpu->pc = ip + 5;
            }
            cpu->cycle++;
            continue;
        }

        // MOV r/m, imm32. Early bring-up supports register-direct /0 only.
        if (op == 0xc7) {
            uint8_t modrm;
            uint32_t imm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            if ((modrm >> 6) != 3 || ((modrm >> 3) & 7) != 0)
                goto undefined;
            if (fetch_u32(cpu, ip + 2, &imm) < 0) goto gpf;
            unsigned rm = (modrm & 7) | ((rex & 0x1) ? 8 : 0);
            uint64_t value = (rex & 0x8) ? (uint64_t)(int64_t)(int32_t)imm : imm;
            x86_64_set_reg(cpu, rm, value);
            cpu->pc = ip + 6;
            cpu->cycle++;
            continue;
        }

        // XOR r/m, r for register-direct operands.
        if (op == 0x31) {
            uint8_t modrm;
            unsigned src, dst;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            if (decode_reg_reg(cpu, rex, modrm, &src, &dst) < 0)
                goto undefined;
            if (rex & 0x8) {
                uint64_t value = x86_64_get_reg(cpu, dst) ^ x86_64_get_reg(cpu, src);
                x86_64_set_reg(cpu, dst, value);
                set_logic_flags(cpu, value, 64);
            } else {
                uint32_t value = (uint32_t)x86_64_get_reg(cpu, dst) ^
                                 (uint32_t)x86_64_get_reg(cpu, src);
                x86_64_set_reg(cpu, dst, value);
                set_logic_flags(cpu, value, 32);
            }
            cpu->pc = ip + 2;
            cpu->cycle++;
            continue;
        }

        // LEA r64, [RIP + disp32]. This is the form used by the first static
        // hello-world fixture to obtain the message address.
        if (op == 0x8d && (rex & 0x8)) {
            uint8_t modrm;
            uint32_t disp_raw;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned mod = modrm >> 6;
            unsigned rm = modrm & 7;
            unsigned dst = ((modrm >> 3) & 7) | ((rex & 0x4) ? 8 : 0);
            if (mod != 0 || rm != 5 || (rex & 0x1))
                goto undefined;
            if (fetch_u32(cpu, ip + 2, &disp_raw) < 0) goto gpf;
            addr_t next = ip + 6;
            x86_64_set_reg(cpu, dst, next + (int32_t)disp_raw);
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // NOP
        if (op == 0x90) {
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // SYSCALL
        if (op == 0x0f) {
            uint8_t op2;
            if (fetch_u8(cpu, ip + 1, &op2) < 0) goto gpf;
            if (op2 == 0x05) {
                uint64_t guest_nr = x86_64_get_rax(cpu);
                int compat_nr = x86_64_to_compat_syscall(guest_nr);
                cpu->pc = ip + 2;
                cpu->cycle++;
                if (compat_nr < 0) {
                    x86_64_set_rax(cpu, (uint64_t)(int64_t)-X86_64_ENOSYS);
                    continue;
                }
                bridge_syscall(cpu, guest_nr, compat_nr);
                cpu->trapno = INT_SYSCALL;
                return INT_SYSCALL;
            }
        }

        // INT3 is useful as an intentional bring-up breakpoint.
        if (op == 0xcc) {
            cpu->pc = ip + 1;
            cpu->trapno = INT_BREAKPOINT;
            return INT_BREAKPOINT;
        }

undefined:
        cpu->segfault_addr = cpu->pc;
        cpu->segfault_was_write = false;
        cpu->trapno = INT_UNDEFINED;
        return INT_UNDEFINED;

gpf:
        cpu->trapno = INT_GPF;
        return INT_GPF;
    }

    cpu->trapno = INT_TIMER;
    return INT_TIMER;
}

void cpu_poke(struct cpu_state *cpu) {
    if (cpu->poked_ptr == NULL)
        cpu->poked_ptr = &cpu->_poked;
    __atomic_store_n(cpu->poked_ptr, true, __ATOMIC_SEQ_CST);
}
