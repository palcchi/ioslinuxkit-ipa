#!/usr/bin/env python3
from pathlib import Path

cpu_h = Path("emu/arch/x86_64/cpu.h")
h = cpu_h.read_text()
field_anchor = '''    union x86_64_xmm xmm[16];\n    union x86_64_xmm fp[32];\n'''
field_insert = '''    union x86_64_xmm xmm[16];\n\n    // Minimal architectural x87 stack used by the direct x86_64 interpreter.\n    // Keep each register in raw 80-bit extended format so this stays correct\n    // on ARM64 hosts where C long double is not necessarily x87 extended.\n    uint8_t x87_st[8][10];\n    uint8_t x87_top;\n    uint8_t x87_valid;\n    uint16_t x87_control;\n    uint8_t x87_control_valid;\n\n    union x86_64_xmm fp[32];\n'''
if field_anchor not in h:
    raise SystemExit("x87 cpu-state anchor missing")
h = h.replace(field_anchor, field_insert, 1)
cpu_h.write_text(h)

interp = Path("emu/arch/x86_64/interp.c")
s = interp.read_text()
helper_anchor = '''static bool condition_true(struct cpu_state *cpu, unsigned cc) {\n'''
helpers = r'''static unsigned x87_phys(const struct cpu_state *cpu, unsigned logical) {
    return (cpu->x87_top + logical) & 7;
}

static bool x87_is_valid(const struct cpu_state *cpu, unsigned logical) {
    return (cpu->x87_valid & (1u << x87_phys(cpu, logical))) != 0;
}

static int x87_push_raw(struct cpu_state *cpu, const uint8_t raw[10]) {
    unsigned top = (cpu->x87_top - 1) & 7;
    // A real x87 raises stack overflow here. During bring-up, surface it as
    // undefined instead of silently destroying a live register.
    if (cpu->x87_valid & (1u << top))
        return -1;
    cpu->x87_top = top;
    memcpy(cpu->x87_st[top], raw, 10);
    cpu->x87_valid |= (uint8_t)(1u << top);
    return 0;
}

static int x87_pop(struct cpu_state *cpu) {
    unsigned top = cpu->x87_top & 7;
    if (!(cpu->x87_valid & (1u << top)))
        return -1;
    cpu->x87_valid &= (uint8_t)~(1u << top);
    cpu->x87_top = (top + 1) & 7;
    return 0;
}

'''
if helper_anchor not in s:
    raise SystemExit("x87 helper anchor missing")
s = s.replace(helper_anchor, helpers + helper_anchor, 1)

# Put x87 dispatch before the ordinary F6/F7 group so the one-byte escape is
# handled while all generic ModRM/SIB machinery is already available.
dispatch_anchor = '''        // TEST r/m, immediate (F7 /0) and NOT/NEG (F7 /2,/3).\n'''
dispatch = r'''        // Minimal x87 raw-stack transport. Modern BDS still reaches an x87
        // long-double return path during startup. Preserve the exact 80-bit
        // payload rather than depending on the ARM64 host long-double format.
        if (op == 0xdb) {
            uint8_t modrm;
            if (fetch_u8(cpu, ip + 1, &modrm) < 0) goto gpf;
            unsigned mod = modrm >> 6;
            unsigned group_raw = (modrm >> 3) & 7;
            if (mod != 3 && (group_raw == 5 || group_raw == 7)) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, 0, &rm, &group, &next) < 0) goto gpf;
                if (rm.is_reg) goto undefined;
                if ((group & 7) == 5) { // FLD m80real
                    uint8_t raw[10];
                    if (guest_read(cpu, rm.addr, raw, sizeof(raw)) < 0) goto gpf;
                    if (x87_push_raw(cpu, raw) < 0) goto undefined;
                } else { // FSTP m80real
                    if (!x87_is_valid(cpu, 0)) goto undefined;
                    unsigned top = x87_phys(cpu, 0);
                    if (guest_write(cpu, rm.addr, cpu->x87_st[top], 10) < 0) goto gpf;
                    if (x87_pop(cpu) < 0) goto undefined;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
        }

        // Common register-stack transports used around long-double call/return
        // sequences: FLD ST(i), FXCH ST(i), and FSTP ST(i).
        if (op == 0xd9) {
            uint8_t b;
            if (fetch_u8(cpu, ip + 1, &b) < 0) goto gpf;
            unsigned mod = b >> 6;
            unsigned group_raw = (b >> 3) & 7;
            if (mod != 3 && (group_raw == 5 || group_raw == 7)) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 1, 2, &rm, &group, &next) < 0) goto gpf;
                if (rm.is_reg) goto undefined;
                if ((group & 7) == 5) { // FLDCW m16
                    uint16_t control;
                    if (guest_read(cpu, rm.addr, &control, sizeof(control)) < 0) goto gpf;
                    cpu->x87_control = control;
                    cpu->x87_control_valid = 1;
                } else { // FNSTCW m16
                    uint16_t control = cpu->x87_control_valid ? cpu->x87_control : 0x037f;
                    if (guest_write(cpu, rm.addr, &control, sizeof(control)) < 0) goto gpf;
                }
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }
            if (b >= 0xc0 && b <= 0xc7) { // FLD ST(i)
                unsigned i = b & 7;
                if (!x87_is_valid(cpu, i)) goto undefined;
                uint8_t raw[10];
                memcpy(raw, cpu->x87_st[x87_phys(cpu, i)], 10);
                if (x87_push_raw(cpu, raw) < 0) goto undefined;
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }
            if (b >= 0xc8 && b <= 0xcf) { // FXCH ST(i)
                unsigned i = b & 7;
                if (!x87_is_valid(cpu, 0) || !x87_is_valid(cpu, i)) goto undefined;
                unsigned a = x87_phys(cpu, 0), c = x87_phys(cpu, i);
                uint8_t tmp[10];
                memcpy(tmp, cpu->x87_st[a], 10);
                memcpy(cpu->x87_st[a], cpu->x87_st[c], 10);
                memcpy(cpu->x87_st[c], tmp, 10);
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }
        }
        if (op == 0xdd) {
            uint8_t b;
            if (fetch_u8(cpu, ip + 1, &b) < 0) goto gpf;
            if (b >= 0xd8 && b <= 0xdf) { // FSTP ST(i)
                unsigned i = b & 7;
                if (!x87_is_valid(cpu, 0) || !x87_is_valid(cpu, i)) goto undefined;
                memcpy(cpu->x87_st[x87_phys(cpu, i)], cpu->x87_st[x87_phys(cpu, 0)], 10);
                if (x87_pop(cpu) < 0) goto undefined;
                cpu->pc = ip + 2;
                cpu->cycle++;
                continue;
            }
        }

'''
if dispatch_anchor not in s:
    raise SystemExit("x87 dispatch anchor missing")
s = s.replace(dispatch_anchor, dispatch + dispatch_anchor, 1)
interp.write_text(s)

# Exact BDS DB /5 m80 load plus DB /7 store round-trip. The payload contains
# deliberately odd bytes so a host floating-point conversion cannot hide bugs.
test = Path("tests/x86_64/direct_guest_smoke.c")
t = test.read_text()
func_anchor = '''static void test_write_exit(void) {\n'''
func = r'''static void test_x87_control_word(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0xd9,0xac,0x24,0x80,0x00,0x00,0x00,
        0xd9,0x7c,0x24,0x16,
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.sp = BASE + 0x200;
    const uint16_t control = 0x027f;
    memcpy(&memory[0x280], &control, sizeof(control));
    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    uint16_t stored = 0;
    memcpy(&stored, &memory[0x216], sizeof(stored));
    assert(stored == control);
    puts("DIRECT X86_64 X87 CONTROL: PASS");
}

static void test_x87_m80_roundtrip(void) {
    memset(memory, 0, sizeof(memory));
    const uint8_t program[] = {
        0xdb,0xac,0x24,0x90,0x00,0x00,0x00, // fld tbyte ptr [rsp+0x90]
        0xdb,0xbc,0x24,0xa0,0x00,0x00,0x00, // fstp tbyte ptr [rsp+0xa0]
        0x48,0xc7,0xc0,0x3c,0x00,0x00,0x00,
        0x48,0x31,0xff,
        0x0f,0x05,
    };
    memcpy(memory, program, sizeof(program));
    const uint8_t payload[10] = {0x01,0x23,0x45,0x67,0x89,0xab,0xcd,0xef,0x34,0x12};

    struct mmu mmu = {.ops = &ops, .asbestos = NULL, .changes = 0};
    struct cpu_state cpu = fresh_cpu(&mmu);
    cpu.sp = BASE + 0x200;
    memcpy(&memory[0x290], payload, sizeof(payload));

    int interrupt = cpu_run_to_interrupt(&cpu, NULL);
    assert(interrupt == INT_SYSCALL);
    assert(cpu.x86_last_syscall == 60);
    assert(memcmp(&memory[0x2a0], payload, sizeof(payload)) == 0);
    assert(cpu.x87_valid == 0);
    puts("DIRECT X86_64 X87 M80: PASS");
}

'''
if func_anchor not in t:
    raise SystemExit("x87 direct-smoke function anchor missing")
t = t.replace(func_anchor, func + func_anchor, 1)
main_anchor = '''    test_write_exit();\n'''
if main_anchor not in t:
    raise SystemExit("x87 direct-smoke main anchor missing")
t = t.replace(main_anchor, '''    test_x87_control_word();\n    test_x87_m80_roundtrip();\n    test_write_exit();\n''', 1)
test.write_text(t)

print("patched x86_64 raw x87 stack with FLD/FSTP m80 and stack transports")
