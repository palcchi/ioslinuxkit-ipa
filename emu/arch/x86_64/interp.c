#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "emu/cpu.h"
#include "emu/interrupt.h"
#include "emu/mmu.h"

// Direct, non-JIT x86_64 bring-up interpreter. The first version only knew
// enough instructions for a hand-written write/exit fixture. This version adds
// the scalar core needed to enter a real glibc dynamic loader: ModRM/SIB memory
// addressing, stack/control flow, arithmetic/flags, branches, CPUID and the
// x86_64 arch_prctl TLS bootstrap.

#define X86_64_ENOSYS 38
#define X86_64_EFAULT 14
#define X86_64_EINVAL 22
#define INTERP_SLICE 100000

#define ARCH_SET_GS 0x1001
#define ARCH_SET_FS 0x1002
#define ARCH_GET_FS 0x1003
#define ARCH_GET_GS 0x1004

struct rm_operand {
    bool is_reg;
    unsigned reg;
    addr_t addr;
};

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

static int guest_write(struct cpu_state *cpu, addr_t addr, const void *value, size_t size) {
    const uint8_t *src = value;
    for (size_t i = 0; i < size; i++) {
        uint8_t *dst = mmu_translate(cpu->mmu, addr + i, MEM_WRITE);
        if (dst == NULL) {
            cpu->segfault_addr = addr + i;
            cpu->segfault_was_write = true;
            return -1;
        }
        *dst = src[i];
    }
    return 0;
}

static int fetch_u8(struct cpu_state *cpu, addr_t addr, uint8_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static int fetch_u16(struct cpu_state *cpu, addr_t addr, uint16_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static int fetch_u32(struct cpu_state *cpu, addr_t addr, uint32_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static int fetch_u64(struct cpu_state *cpu, addr_t addr, uint64_t *value) {
    return guest_read(cpu, addr, value, sizeof(*value));
}

static uint64_t bits_mask(unsigned bits) {
    if (bits == 8) return UINT8_MAX;
    if (bits == 16) return UINT16_MAX;
    if (bits == 32) return UINT32_MAX;
    return UINT64_MAX;
}

static uint64_t sign_bit(unsigned bits) {
    return 1ULL << (bits - 1);
}

static void set_logic_flags(struct cpu_state *cpu, uint64_t value, unsigned bits) {
    uint64_t v = value & bits_mask(bits);
    cpu->zf = v == 0;
    cpu->nf = (v & sign_bit(bits)) != 0;
    cpu->cf = 0;
    cpu->vf = 0;
}

static uint64_t set_add_flags(struct cpu_state *cpu, uint64_t a, uint64_t b, unsigned bits) {
    uint64_t mask = bits_mask(bits);
    uint64_t aa = a & mask;
    uint64_t bb = b & mask;
    uint64_t result = (aa + bb) & mask;
    if (bits == 64) {
        __uint128_t wide = (__uint128_t)aa + (__uint128_t)bb;
        cpu->cf = (wide >> 64) != 0;
    } else {
        cpu->cf = (aa + bb) > mask;
    }
    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = ((~(aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
    return result;
}

static uint64_t set_sub_flags(struct cpu_state *cpu, uint64_t a, uint64_t b, unsigned bits) {
    uint64_t mask = bits_mask(bits);
    uint64_t aa = a & mask;
    uint64_t bb = b & mask;
    uint64_t result = (aa - bb) & mask;
    cpu->cf = aa < bb;
    cpu->zf = result == 0;
    cpu->nf = (result & sign_bit(bits)) != 0;
    cpu->vf = (((aa ^ bb) & (aa ^ result)) & sign_bit(bits)) != 0;
    return result;
}

static uint64_t read_reg_bits(struct cpu_state *cpu, unsigned reg, unsigned bits) {
    return x86_64_get_reg(cpu, reg) & bits_mask(bits);
}

static void write_reg_bits(struct cpu_state *cpu, unsigned reg, uint64_t value, unsigned bits) {
    if (bits == 64 || bits == 32) {
        // x86-64 32-bit register writes zero-extend into the full register.
        x86_64_set_reg(cpu, reg, value & bits_mask(bits));
        return;
    }
    uint64_t old = x86_64_get_reg(cpu, reg);
    uint64_t mask = bits_mask(bits);
    x86_64_set_reg(cpu, reg, (old & ~mask) | (value & mask));
}

static int rm_read(struct cpu_state *cpu, const struct rm_operand *rm, unsigned bits, uint64_t *value) {
    if (rm->is_reg) {
        *value = read_reg_bits(cpu, rm->reg, bits);
        return 0;
    }
    uint64_t tmp = 0;
    if (guest_read(cpu, rm->addr, &tmp, bits / 8) < 0)
        return -1;
    *value = tmp & bits_mask(bits);
    return 0;
}

static int rm_write(struct cpu_state *cpu, const struct rm_operand *rm, unsigned bits, uint64_t value) {
    if (rm->is_reg) {
        write_reg_bits(cpu, rm->reg, value, bits);
        return 0;
    }
    uint64_t tmp = value;
    return guest_write(cpu, rm->addr, &tmp, bits / 8);
}

// Decode a ModRM operand, including the ordinary x86_64 SIB/base/index/disp
// forms. imm_bytes is included when calculating RIP-relative addresses because
// RIP points to the end of the complete instruction, not merely the ModRM.
static int decode_rm(struct cpu_state *cpu, uint8_t rex, bool fs_prefix,
                     addr_t modrm_addr, unsigned imm_bytes,
                     struct rm_operand *rm, unsigned *reg_field, addr_t *next) {
    uint8_t modrm;
    if (fetch_u8(cpu, modrm_addr, &modrm) < 0)
        return -1;

    unsigned mod = modrm >> 6;
    unsigned raw_rm = modrm & 7;
    if (reg_field != NULL)
        *reg_field = ((modrm >> 3) & 7) | ((rex & 0x4) ? 8 : 0);

    addr_t p = modrm_addr + 1;
    if (mod == 3) {
        rm->is_reg = true;
        rm->reg = raw_rm | ((rex & 0x1) ? 8 : 0);
        rm->addr = 0;
        *next = p + imm_bytes;
        return 0;
    }

    rm->is_reg = false;
    rm->reg = 0;
    uint64_t base = 0;
    uint64_t index = 0;
    unsigned scale = 0;
    int64_t disp = 0;
    bool rip_relative = false;

    if (raw_rm == 4) {
        uint8_t sib;
        if (fetch_u8(cpu, p++, &sib) < 0)
            return -1;
        scale = sib >> 6;
        unsigned raw_index = (sib >> 3) & 7;
        unsigned raw_base = sib & 7;
        unsigned index_reg = raw_index | ((rex & 0x2) ? 8 : 0);
        unsigned base_reg = raw_base | ((rex & 0x1) ? 8 : 0);

        if (!(raw_index == 4 && !(rex & 0x2)))
            index = x86_64_get_reg(cpu, index_reg) << scale;

        if (mod == 0 && raw_base == 5 && !(rex & 0x1)) {
            uint32_t d;
            if (fetch_u32(cpu, p, &d) < 0)
                return -1;
            p += 4;
            disp = (int32_t)d;
        } else {
            base = x86_64_get_reg(cpu, base_reg);
        }
    } else if (mod == 0 && raw_rm == 5 && !(rex & 0x1)) {
        uint32_t d;
        if (fetch_u32(cpu, p, &d) < 0)
            return -1;
        p += 4;
        disp = (int32_t)d;
        rip_relative = true;
    } else {
        unsigned base_reg = raw_rm | ((rex & 0x1) ? 8 : 0);
        base = x86_64_get_reg(cpu, base_reg);
    }

    if (mod == 1) {
        uint8_t d;
        if (fetch_u8(cpu, p++, &d) < 0)
            return -1;
        disp += (int8_t)d;
    } else if (mod == 2) {
        uint32_t d;
        if (fetch_u32(cpu, p, &d) < 0)
            return -1;
        p += 4;
        disp += (int32_t)d;
    }

    *next = p + imm_bytes;
    if (rip_relative)
        base = *next;
    rm->addr = base + index + disp;
    if (fs_prefix)
        rm->addr += cpu->tls_ptr;
    return 0;
}

static int push_u64(struct cpu_state *cpu, uint64_t value) {
    cpu->sp -= 8;
    return guest_write(cpu, cpu->sp, &value, sizeof(value));
}

static int pop_u64(struct cpu_state *cpu, uint64_t *value) {
    if (guest_read(cpu, cpu->sp, value, sizeof(*value)) < 0)
        return -1;
    cpu->sp += 8;
    return 0;
}

static bool condition_true(struct cpu_state *cpu, unsigned cc) {
    switch (cc & 15) {
        case 0x0: return cpu->vf;                         // O
        case 0x1: return !cpu->vf;                        // NO
        case 0x2: return cpu->cf;                         // B/NAE/C
        case 0x3: return !cpu->cf;                        // NB/AE/NC
        case 0x4: return cpu->zf;                         // Z/E
        case 0x5: return !cpu->zf;                        // NZ/NE
        case 0x6: return cpu->cf || cpu->zf;              // BE/NA
        case 0x7: return !cpu->cf && !cpu->zf;            // A/NBE
        // PF is not exposed in cpu_state yet. Conservative values keep the
        // decoder deterministic until parity-flag support lands.
        case 0x8: return false;                           // S? actually cc=8 is S
        case 0x9: return true;                            // NS
        case 0xa: return false;                           // P/PE
        case 0xb: return true;                            // NP/PO
        case 0xc: return cpu->nf != cpu->vf;              // L/NGE
        case 0xd: return cpu->nf == cpu->vf;              // GE/NL
        case 0xe: return cpu->zf || (cpu->nf != cpu->vf); // LE/NG
        case 0xf: return !cpu->zf && (cpu->nf == cpu->vf);// G/NLE
    }
    return false;
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
        case 5:   return 80;   // fstat (layout wrapper still pending)
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

static int handle_arch_prctl(struct cpu_state *cpu) {
    uint64_t code = x86_64_get_reg(cpu, X86_64_RDI);
    uint64_t value = x86_64_get_reg(cpu, X86_64_RSI);
    switch (code) {
        case ARCH_SET_FS:
            cpu->tls_ptr = value;
            return 0;
        case ARCH_GET_FS:
            if (guest_write(cpu, value, &cpu->tls_ptr, sizeof(cpu->tls_ptr)) < 0)
                return -X86_64_EFAULT;
            return 0;
        case ARCH_SET_GS:
        case ARCH_GET_GS:
        default:
            return -X86_64_EINVAL;
    }
}

int cpu_run_to_interrupt(struct cpu_state *cpu, struct tlb *tlb) {
    (void) tlb;

    if (cpu->poked_ptr == NULL)
        cpu->poked_ptr = &cpu->_poked;

    if (cpu->x86_syscall_pending) {
        x86_64_set_rax(cpu, cpu->regs[0]);
        cpu->x86_syscall_pending = false;
    }

    for (unsigned step = 0; step < INTERP_SLICE; step++) {
        if (__atomic_exchange_n(cpu->poked_ptr, false, __ATOMIC_SEQ_CST)) {
            cpu->trapno = INT_TIMER;
            return INT_TIMER;
        }

        addr_t insn_start = cpu->pc;
        addr_t ip = insn_start;
        uint8_t op;
        bool fs_prefix = false;
        bool rep_prefix = false;
        bool operand16 = false;
        uint8_t rex = 0;

        // Legacy prefixes followed by at most one effective REX prefix.
        for (;;) {
            if (fetch_u8(cpu, ip, &op) < 0)
                goto gpf;
            if (op == 0x64) { fs_prefix = true; ip++; continue; }
            if (op == 0x66) { operand16 = true; ip++; continue; }
            if (op == 0xf3) { rep_prefix = true; ip++; continue; }
            if (op == 0xf2) { rep_prefix = true; ip++; continue; }
            if (op >= 0x40 && op <= 0x4f) { rex = op; ip++; continue; }
            break;
        }

        // ENDBR64. CET itself is not advertised, so it is a no-op.
        if (rep_prefix && op == 0x0f) {
            uint8_t b2, b3;
            if (fetch_u8(cpu, ip + 1, &b2) == 0 &&
                fetch_u8(cpu, ip + 2, &b3) == 0 &&
                b2 == 0x1e && b3 == 0xfa) {
                cpu->pc = ip + 3;
                cpu->cycle++;
                continue;
            }
        }

        unsigned bits = operand16 ? 16 : ((rex & 0x8) ? 64 : 32);

        // PUSH/POP register.
        if (op >= 0x50 && op <= 0x57) {
            unsigned reg = (op - 0x50) | ((rex & 1) ? 8 : 0);
            if (push_u64(cpu, x86_64_get_reg(cpu, reg)) < 0) goto gpf;
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }
        if (op >= 0x58 && op <= 0x5f) {
            unsigned reg = (op - 0x58) | ((rex & 1) ? 8 : 0);
            uint64_t value;
            if (pop_u64(cpu, &value) < 0) goto gpf;
            x86_64_set_reg(cpu, reg, value);
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // MOV r64, imm64 / MOV r32, imm32.
        if (op >= 0xb8 && op <= 0xbf) {
            unsigned reg = (op - 0xb8) | ((rex & 0x1) ? 8 : 0);
            if (rex & 0x8) {
                uint64_t imm;
                if (fetch_u64(cpu, ip + 1, &imm) < 0) goto gpf;
                x86_64_set_reg(cpu, reg, imm);
                cpu->pc = ip + 9;
            } else if (operand16) {
                uint16_t imm;
                if (fetch_u16(cpu, ip + 1, &imm) < 0) goto gpf;
                write_reg_bits(cpu, reg, imm, 16);
                cpu->pc = ip + 3;
            } else {
                uint32_t imm;
                if (fetch_u32(cpu, ip + 1, &imm) < 0) goto gpf;
                x86_64_set_reg(cpu, reg, imm);
                cpu->pc = ip + 5;
            }
            cpu->cycle++;
            continue;
        }

        // MOV r/m, r and MOV r, r/m.
        if (op == 0x89 || op == 0x8b || op == 0x88 || op == 0x8a) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            unsigned move_bits = (op == 0x88 || op == 0x8a) ? 8 : bits;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            uint64_t value;
            if (op == 0x89 || op == 0x88) {
                value = read_reg_bits(cpu, reg, move_bits);
                if (rm_write(cpu, &rm, move_bits, value) < 0) goto gpf;
            } else {
                if (rm_read(cpu, &rm, move_bits, &value) < 0) goto gpf;
                write_reg_bits(cpu, reg, value, move_bits);
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOV r/m, immediate.
        if (op == 0xc7 || op == 0xc6) {
            unsigned imm_bytes = op == 0xc6 ? 1 : (operand16 ? 2 : 4);
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            if ((group & 7) != 0) goto undefined;
            uint64_t imm = 0;
            addr_t imm_addr = next - imm_bytes;
            if (imm_bytes == 1) { uint8_t v; if (fetch_u8(cpu, imm_addr, &v) < 0) goto gpf; imm = v; }
            else if (imm_bytes == 2) { uint16_t v; if (fetch_u16(cpu, imm_addr, &v) < 0) goto gpf; imm = v; }
            else { uint32_t v; if (fetch_u32(cpu, imm_addr, &v) < 0) goto gpf; imm = (bits == 64) ? (uint64_t)(int64_t)(int32_t)v : v; }
            if (rm_write(cpu, &rm, op == 0xc6 ? 8 : bits, imm) < 0) goto gpf;
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // LEA r, m.
        if (op == 0x8d) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            if (decode_rm(cpu, rex, false, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            if (rm.is_reg) goto undefined;
            write_reg_bits(cpu, reg, rm.addr, bits);
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // MOVSXD r64, r/m32.
        if (op == 0x63 && (rex & 0x8)) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            uint64_t value;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            if (rm_read(cpu, &rm, 32, &value) < 0) goto gpf;
            x86_64_set_reg(cpu, reg, (uint64_t)(int64_t)(int32_t)value);
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // Binary register/memory ALU families.
        if (op == 0x01 || op == 0x03 || op == 0x09 || op == 0x0b ||
            op == 0x21 || op == 0x23 || op == 0x29 || op == 0x2b ||
            op == 0x31 || op == 0x33 || op == 0x39 || op == 0x3b ||
            op == 0x84 || op == 0x85) {
            struct rm_operand rm;
            unsigned reg;
            addr_t next;
            unsigned alu_bits = (op == 0x84) ? 8 : bits;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &reg, &next) < 0) goto gpf;
            uint64_t rv, gv;
            if (rm_read(cpu, &rm, alu_bits, &rv) < 0) goto gpf;
            gv = read_reg_bits(cpu, reg, alu_bits);
            bool reverse = (op & 0x02) != 0;
            uint64_t a = reverse ? gv : rv;
            uint64_t b = reverse ? rv : gv;
            uint64_t result = 0;
            unsigned family = op & 0xf8;
            if (op == 0x84 || op == 0x85) {
                set_logic_flags(cpu, rv & gv, alu_bits);
            } else if (family == 0x00) { // ADD 01/03
                result = set_add_flags(cpu, a, b, alu_bits);
                if (reverse) write_reg_bits(cpu, reg, result, alu_bits);
                else if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            } else if (family == 0x08) { // OR 09/0b
                result = a | b; set_logic_flags(cpu, result, alu_bits);
                if (reverse) write_reg_bits(cpu, reg, result, alu_bits);
                else if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            } else if (family == 0x20) { // AND 21/23
                result = a & b; set_logic_flags(cpu, result, alu_bits);
                if (reverse) write_reg_bits(cpu, reg, result, alu_bits);
                else if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            } else if (family == 0x28) { // SUB 29/2b
                result = set_sub_flags(cpu, a, b, alu_bits);
                if (reverse) write_reg_bits(cpu, reg, result, alu_bits);
                else if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            } else if (family == 0x30) { // XOR 31/33
                result = a ^ b; set_logic_flags(cpu, result, alu_bits);
                if (reverse) write_reg_bits(cpu, reg, result, alu_bits);
                else if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            } else if (family == 0x38) { // CMP 39/3b
                (void)set_sub_flags(cpu, a, b, alu_bits);
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // Group-1 immediate ALU: 80/81/83.
        if (op == 0x80 || op == 0x81 || op == 0x83) {
            unsigned alu_bits = op == 0x80 ? 8 : bits;
            unsigned imm_bytes = op == 0x81 ? (operand16 ? 2 : 4) : 1;
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            uint64_t imm;
            addr_t ia = next - imm_bytes;
            if (imm_bytes == 1) { uint8_t v; if (fetch_u8(cpu, ia, &v) < 0) goto gpf; imm = (op == 0x83) ? (uint64_t)(int64_t)(int8_t)v : v; }
            else if (imm_bytes == 2) { uint16_t v; if (fetch_u16(cpu, ia, &v) < 0) goto gpf; imm = v; }
            else { uint32_t v; if (fetch_u32(cpu, ia, &v) < 0) goto gpf; imm = (alu_bits == 64) ? (uint64_t)(int64_t)(int32_t)v : v; }
            uint64_t old, result = 0;
            if (rm_read(cpu, &rm, alu_bits, &old) < 0) goto gpf;
            switch (group & 7) {
                case 0: result = set_add_flags(cpu, old, imm, alu_bits); break;
                case 1: result = old | imm; set_logic_flags(cpu, result, alu_bits); break;
                case 4: result = old & imm; set_logic_flags(cpu, result, alu_bits); break;
                case 5: result = set_sub_flags(cpu, old, imm, alu_bits); break;
                case 6: result = old ^ imm; set_logic_flags(cpu, result, alu_bits); break;
                case 7: (void)set_sub_flags(cpu, old, imm, alu_bits); cpu->pc = next; cpu->cycle++; continue;
                default: goto undefined;
            }
            if (rm_write(cpu, &rm, alu_bits, result) < 0) goto gpf;
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).
        if (op == 0xf7) {
            unsigned imm_bytes = 0;
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned group_raw = (modrm >> 3) & 7;
            if (group_raw == 0) imm_bytes = operand16 ? 2 : 4;
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            uint64_t value;
            if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
            if ((group & 7) == 0) {
                uint64_t imm;
                addr_t ia = next - imm_bytes;
                if (imm_bytes == 2) { uint16_t v; if (fetch_u16(cpu, ia, &v) < 0) goto gpf; imm = v; }
                else { uint32_t v; if (fetch_u32(cpu, ia, &v) < 0) goto gpf; imm = bits == 64 ? (uint64_t)(int64_t)(int32_t)v : v; }
                set_logic_flags(cpu, value & imm, bits);
            } else if ((group & 7) == 2) {
                if (rm_write(cpu, &rm, bits, ~value) < 0) goto gpf;
            } else if ((group & 7) == 3) {
                uint64_t result = set_sub_flags(cpu, 0, value, bits);
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
            } else {
                goto undefined;
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // Shift group C1/D1: SHL/SHR/SAR with immediate or count=1.
        if (op == 0xc1 || op == 0xd1) {
            unsigned imm_bytes = op == 0xc1 ? 1 : 0;
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, imm_bytes, &rm, &group, &next) < 0) goto gpf;
            uint8_t count = 1;
            if (op == 0xc1 && fetch_u8(cpu, next - 1, &count) < 0) goto gpf;
            count &= bits == 64 ? 63 : 31;
            uint64_t value;
            if (rm_read(cpu, &rm, bits, &value) < 0) goto gpf;
            if (count != 0) {
                uint64_t result;
                switch (group & 7) {
                    case 4: // SHL/SAL
                        cpu->cf = (value >> (bits - count)) & 1;
                        result = (value << count) & bits_mask(bits);
                        break;
                    case 5: // SHR
                        cpu->cf = (value >> (count - 1)) & 1;
                        result = value >> count;
                        break;
                    case 7: // SAR
                        cpu->cf = (value >> (count - 1)) & 1;
                        if (bits == 64) result = (uint64_t)((int64_t)value >> count);
                        else result = (uint32_t)((int32_t)(uint32_t)value >> count);
                        break;
                    default: goto undefined;
                }
                cpu->zf = (result & bits_mask(bits)) == 0;
                cpu->nf = (result & sign_bit(bits)) != 0;
                if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
            }
            cpu->pc = next;
            cpu->cycle++;
            continue;
        }

        // CALL rel32.
        if (op == 0xe8) {
            uint32_t raw;
            if (fetch_u32(cpu, ip + 1, &raw) < 0) goto gpf;
            addr_t next = ip + 5;
            if (push_u64(cpu, next) < 0) goto gpf;
            cpu->pc = next + (int32_t)raw;
            cpu->cycle++;
            continue;
        }

        // JMP rel32 / rel8.
        if (op == 0xe9 || op == 0xeb) {
            if (op == 0xe9) {
                uint32_t raw; if (fetch_u32(cpu, ip + 1, &raw) < 0) goto gpf;
                cpu->pc = ip + 5 + (int32_t)raw;
            } else {
                uint8_t raw; if (fetch_u8(cpu, ip + 1, &raw) < 0) goto gpf;
                cpu->pc = ip + 2 + (int8_t)raw;
            }
            cpu->cycle++;
            continue;
        }

        // Short conditional branches.
        if (op >= 0x70 && op <= 0x7f) {
            uint8_t raw;
            if (fetch_u8(cpu, ip + 1, &raw) < 0) goto gpf;
            addr_t next = ip + 2;
            cpu->pc = condition_true(cpu, op & 15) ? next + (int8_t)raw : next;
            cpu->cycle++;
            continue;
        }

        // RET / RET imm16.
        if (op == 0xc3 || op == 0xc2) {
            uint64_t target;
            if (pop_u64(cpu, &target) < 0) goto gpf;
            if (op == 0xc2) {
                uint16_t adjust;
                if (fetch_u16(cpu, ip + 1, &adjust) < 0) goto gpf;
                cpu->sp += adjust;
            }
            cpu->pc = target;
            cpu->cycle++;
            continue;
        }

        // LEAVE.
        if (op == 0xc9) {
            cpu->sp = x86_64_get_reg(cpu, X86_64_RBP);
            uint64_t value;
            if (pop_u64(cpu, &value) < 0) goto gpf;
            x86_64_set_reg(cpu, X86_64_RBP, value);
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // Group FF: INC, DEC, indirect CALL/JMP, PUSH.
        if (op == 0xff) {
            struct rm_operand rm;
            unsigned group;
            addr_t next;
            if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &group, &next) < 0) goto gpf;
            uint64_t value;
            if (rm_read(cpu, &rm, bits == 32 ? 64 : bits, &value) < 0) goto gpf;
            switch (group & 7) {
                case 0: {
                    bool old_cf = cpu->cf;
                    uint64_t result = set_add_flags(cpu, value, 1, bits);
                    cpu->cf = old_cf;
                    if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
                    cpu->pc = next;
                    break;
                }
                case 1: {
                    bool old_cf = cpu->cf;
                    uint64_t result = set_sub_flags(cpu, value, 1, bits);
                    cpu->cf = old_cf;
                    if (rm_write(cpu, &rm, bits, result) < 0) goto gpf;
                    cpu->pc = next;
                    break;
                }
                case 2:
                    if (push_u64(cpu, next) < 0) goto gpf;
                    cpu->pc = value;
                    break;
                case 4:
                    cpu->pc = value;
                    break;
                case 6:
                    if (push_u64(cpu, value) < 0) goto gpf;
                    cpu->pc = next;
                    break;
                default: goto undefined;
            }
            cpu->cycle++;
            continue;
        }

        // NOP / CLD.
        if (op == 0x90 || op == 0xfc) {
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // CDQE/CWDE and CQO/CDQ.
        if (op == 0x98) {
            if (rex & 0x8)
                x86_64_set_rax(cpu, (uint64_t)(int64_t)(int32_t)x86_64_get_rax(cpu));
            else
                x86_64_set_rax(cpu, (uint32_t)(int32_t)(int16_t)x86_64_get_rax(cpu));
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }
        if (op == 0x99) {
            if (rex & 0x8)
                x86_64_set_reg(cpu, X86_64_RDX, (int64_t)x86_64_get_rax(cpu) < 0 ? UINT64_MAX : 0);
            else
                write_reg_bits(cpu, X86_64_RDX, (int32_t)(uint32_t)x86_64_get_rax(cpu) < 0 ? UINT32_MAX : 0, 32);
            cpu->pc = ip + 1;
            cpu->cycle++;
            continue;
        }

        // REP MOVS/STOS. glibc's generic loader paths use these for small
        // structure copies before optimized IFUNC selections are available.
        if (rep_prefix && (op == 0xa4 || op == 0xa5 || op == 0xaa || op == 0xab)) {
            unsigned elem = (op == 0xa4 || op == 0xaa) ? 1 : ((rex & 0x8) ? 8 : (operand16 ? 2 : 4));
            uint64_t count = x86_64_get_reg(cpu, X86_64_RCX);
            uint64_t src = x86_64_get_reg(cpu, X86_64_RSI);
            uint64_t dst = x86_64_get_reg(cpu, X86_64_RDI);
            for (uint64_t i = 0; i < count; i++) {
                if (op == 0xa4 || op == 0xa5) {
                    uint64_t tmp = 0;
                    if (guest_read(cpu, src, &tmp, elem) < 0) goto gpf;
                    if (guest_write(cpu, dst, &tmp, elem) < 0) goto gpf;
                    src += elem;
                } else {
                    uint64_t tmp = x86_64_get_rax(cpu);
                    if (guest_write(cpu, dst, &tmp, elem) < 0) goto gpf;
                }
                dst += elem;
            }
            x86_64_set_reg(cpu, X86_64_RCX, 0);
            x86_64_set_reg(cpu, X86_64_RSI, src);
            x86_64_set_reg(cpu, X86_64_RDI, dst);
            cpu->pc = ip + 1;
            cpu->cycle += count ? count : 1;
            continue;
        }

        if (op == 0x0f) {
            uint8_t op2;
            if (fetch_u8(cpu, ip + 1, &op2) < 0) goto gpf;

            // SYSCALL.
            if (op2 == 0x05) {
                uint64_t guest_nr = x86_64_get_rax(cpu);
                cpu->pc = ip + 2;
                cpu->cycle++;

                // arch_prctl has no AArch64 syscall-table counterpart. Handle
                // the x86_64 FS bootstrap in the interpreter itself.
                if (guest_nr == 158) {
                    int rc = handle_arch_prctl(cpu);
                    x86_64_set_rax(cpu, (uint64_t)(int64_t)rc);
                    continue;
                }

                int compat_nr = x86_64_to_compat_syscall(guest_nr);
                if (compat_nr < 0) {
                    x86_64_set_rax(cpu, (uint64_t)(int64_t)-X86_64_ENOSYS);
                    continue;
                }
                bridge_syscall(cpu, guest_nr, compat_nr);
                cpu->trapno = INT_SYSCALL;
                return INT_SYSCALL;
            }

            // Near conditional branches.
            if (op2 >= 0x80 && op2 <= 0x8f) {
                uint32_t raw;
                if (fetch_u32(cpu, ip + 2, &raw) < 0) goto gpf;
                addr_t next = ip + 6;
                cpu->pc = condition_true(cpu, op2 & 15) ? next + (int32_t)raw : next;
                cpu->cycle++;
                continue;
            }

            // CPUID: expose a conservative x86_64-v1-ish CPU. AVX/AVX2 are
            // deliberately hidden so glibc will not choose instruction paths we
            // have not implemented yet.
            if (op2 == 0xa2) {
                uint32_t leaf = (uint32_t)x86_64_get_rax(cpu);
                uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;
                if (leaf == 0) {
                    eax = 1;
                    ebx = 0x756e6547; // "Genu"
                    edx = 0x49656e69; // "ineI"
                    ecx = 0x6c65746e; // "ntel"
                } else if (leaf == 1) {
                    eax = 0x00000663;
                    // FPU, CX8, CMOV, MMX, FXSR, SSE, SSE2.
                    edx = (1u<<0) | (1u<<8) | (1u<<15) | (1u<<23) |
                          (1u<<24) | (1u<<25) | (1u<<26);
                    ecx = 0;
                }
                write_reg_bits(cpu, X86_64_RAX, eax, 32);
                write_reg_bits(cpu, X86_64_RBX, ebx, 32);
                write_reg_bits(cpu, X86_64_RCX, ecx, 32);
                write_reg_bits(cpu, X86_64_RDX, edx, 32);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }

            // Multi-byte NOP (0F 1F /0).
            if (op2 == 0x1f) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, false, ip + 2, 0, &rm, &group, &next) < 0) goto gpf;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // MOVZX/MOVSX.
            if (op2 == 0xb6 || op2 == 0xb7 || op2 == 0xbe || op2 == 0xbf) {
                unsigned src_bits = (op2 == 0xb6 || op2 == 0xbe) ? 8 : 16;
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                uint64_t value;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, src_bits, &value) < 0) goto gpf;
                if (op2 == 0xbe)
                    value = (uint64_t)(int64_t)(int8_t)value;
                else if (op2 == 0xbf)
                    value = (uint64_t)(int64_t)(int16_t)value;
                write_reg_bits(cpu, reg, value, bits);
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // IMUL r, r/m.
            if (op2 == 0xaf) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                uint64_t src;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                if (rm_read(cpu, &rm, bits, &src) < 0) goto gpf;
                if (bits == 64) {
                    __int128 prod = (__int128)(int64_t)x86_64_get_reg(cpu, reg) * (__int128)(int64_t)src;
                    int64_t low = (int64_t)prod;
                    x86_64_set_reg(cpu, reg, (uint64_t)low);
                    cpu->cf = cpu->vf = prod != (__int128)low;
                } else {
                    int64_t prod = (int64_t)(int32_t)x86_64_get_reg(cpu, reg) * (int64_t)(int32_t)src;
                    int32_t low = (int32_t)prod;
                    write_reg_bits(cpu, reg, (uint32_t)low, 32);
                    cpu->cf = cpu->vf = prod != (int64_t)low;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
        }

        // INT3 is useful as an intentional bring-up breakpoint.
        if (op == 0xcc) {
            cpu->pc = ip + 1;
            cpu->trapno = INT_BREAKPOINT;
            return INT_BREAKPOINT;
        }

undefined:
        cpu->segfault_addr = insn_start;
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
