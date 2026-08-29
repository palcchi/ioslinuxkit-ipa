# Direct x86_64 guest bring-up

Status: experimental, isolated on the `x86_64-guest` branch.

The goal is to execute Linux x86_64 guest instructions directly inside the
LinuxKit/iSH userspace kernel, without running `qemu-x86_64` as a program inside
the ARM64 guest. The production ARM64 backend remains unchanged.

## Milestone 1: direct instruction execution

`emu/arch/x86_64/interp.c` is a non-JIT C interpreter. The first smoke program
executes real x86_64 instruction bytes for `mov`, RIP-relative `lea`, `xor`, and
`syscall`. The syscall bridge translates the x86_64 Linux register convention
(`rax`, `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`) into the shared kernel's current
compatibility view.

This milestone proves the desired architecture shape:

```
x86_64 guest instruction stream
        |
        v
direct C interpreter in the iOS/LinuxKit process
        |
        v
LinuxKit userspace kernel + fakefs + sockets
        |
        v
iOS ARM64 host
```

There is no nested qemu process in this path.

## Remaining work before Bedrock Dedicated Server

1. Wire `guest_arch=x86_64` through Meson and the iOS target.
2. Accept `EM_X86_64` ELF files and report the x86_64 platform string.
3. Replace the early syscall-number bridge with a native x86_64 syscall table,
   including x86_64 structure layouts and `arch_prctl` TLS setup.
4. Implement the x86_64 signal frame and restart ABI.
5. Expand the decoder/executor substantially: ModRM/SIB addressing, arithmetic,
   branches, stack/call/ret, atomics, SSE2, SSSE3/SSE4, and the instruction
   subset actually exercised by glibc and `bedrock_server`.
6. Add x86_64 VDSO handling or explicitly provide the required syscall fallbacks.
7. Build an x86_64 rootfs lane and boot progressively larger fixtures before
   attempting glibc and Bedrock Dedicated Server.

The branch must not replace the working ARM64 target until these gates pass.
