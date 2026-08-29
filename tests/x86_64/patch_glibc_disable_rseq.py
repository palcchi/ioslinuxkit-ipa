from pathlib import Path

p = Path("emu/arch/x86_64/interp.c")
s = p.read_text()
old = "        case 334: return 293;  // rseq\n"
new = "        // x86_64 rseq is intentionally not bridged to the AArch64 ABI yet.\n        // Returning ENOSYS is Linux-compatible and makes glibc use its fallback\n        // path instead of registering an rseq area with a mismatched ABI.\n"
if old not in s:
    raise SystemExit("rseq syscall mapping not found")
p.write_text(s.replace(old, new, 1))
print("patched x86_64 syscall bridge to return ENOSYS for rseq")
