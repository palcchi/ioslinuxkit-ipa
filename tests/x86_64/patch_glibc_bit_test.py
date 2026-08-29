from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
anchor = '''            // CPUID: expose a conservative x86_64-v1-ish CPU. AVX/AVX2 are
'''
if anchor not in s:
    raise SystemExit("CPUID anchor not found")
code = r'''            // BT/BTS/BTR/BTC r/m, r.  Dynamic loaders use BT for compact
            // feature-set membership tests.  For register operands the index is
            // masked by operand width; for memory operands x86 lets the index
            // select a neighboring element as well.
            if (op2 == 0xa3 || op2 == 0xab || op2 == 0xb3 || op2 == 0xbb) {
                struct rm_operand rm;
                unsigned reg;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 0, &rm, &reg, &next) < 0) goto gpf;
                uint64_t raw_index = x86_64_get_reg(cpu, reg);
                unsigned width = bits;
                unsigned bit;
                uint64_t value;
                struct rm_operand target = rm;
                if (rm.is_reg) {
                    bit = (unsigned)(raw_index & (width - 1));
                    if (rm_read(cpu, &target, width, &value) < 0) goto gpf;
                } else {
                    int64_t signed_index = (int64_t)raw_index;
                    int64_t elem = signed_index / (int64_t)width;
                    int64_t rem = signed_index % (int64_t)width;
                    if (rem < 0) { rem += width; elem--; }
                    target.addr += elem * (int64_t)(width / 8);
                    bit = (unsigned)rem;
                    if (rm_read(cpu, &target, width, &value) < 0) goto gpf;
                }
                uint64_t mask = 1ULL << bit;
                cpu->cf = (value & mask) != 0;
                if (op2 == 0xab) value |= mask;       // BTS
                else if (op2 == 0xb3) value &= ~mask; // BTR
                else if (op2 == 0xbb) value ^= mask;  // BTC
                if (op2 != 0xa3 && rm_write(cpu, &target, width, value) < 0) goto gpf;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

            // BT/BTS/BTR/BTC r/m, imm8 (0F BA /4..7).
            if (op2 == 0xba) {
                struct rm_operand rm;
                unsigned group;
                addr_t next;
                if (decode_rm(cpu, rex, fs_prefix, ip + 2, 1, &rm, &group, &next) < 0) goto gpf;
                if ((group & 7) < 4) goto undefined;
                uint8_t imm;
                if (fetch_u8(cpu, next - 1, &imm) < 0) goto gpf;
                unsigned width = bits;
                unsigned bit = imm & (width - 1);
                struct rm_operand target = rm;
                if (!rm.is_reg)
                    target.addr += (imm / width) * (width / 8);
                uint64_t value;
                if (rm_read(cpu, &target, width, &value) < 0) goto gpf;
                uint64_t mask = 1ULL << bit;
                cpu->cf = (value & mask) != 0;
                if ((group & 7) == 5) value |= mask;
                else if ((group & 7) == 6) value &= ~mask;
                else if ((group & 7) == 7) value ^= mask;
                if ((group & 7) != 4 && rm_write(cpu, &target, width, value) < 0) goto gpf;
                cpu->pc = next;
                cpu->cycle++;
                continue;
            }

'''
p.write_text(s.replace(anchor, code + anchor, 1))
print("patched x86_64 interpreter with BT/BTS/BTR/BTC")
