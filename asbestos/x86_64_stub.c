#include <signal.h>
#include <stdlib.h>
#include "asbestos/asbestos.h"
#include "kernel/calls.h"
#include "kernel/errno.h"

// Shared memory/TLB code still exposes a handful of ARM64-JIT diagnostics.
// The direct x86_64 interpreter has no JIT, so these are inert compatibility
// hooks rather than dragging the ARM64 threaded-code backend into the build.
__thread volatile sig_atomic_t in_jit;
volatile addr_t g_watch_page_val = 0;

void c_watch_write_hit(addr_t addr, const char *caller) {
    (void) addr;
    (void) caller;
}

// The current syscall bridge temporarily reuses the existing AArch64 table.
// Provide the LP64 mmap entry it references. mmap2 accepts an offset in pages,
// while Linux x86_64 mmap supplies a byte offset.
addr_t sys_mmap64(addr_t addr, addr_t len, dword_t prot, dword_t flags,
                  fd_t fd_no, qword_t offset) {
    if ((offset & (PAGE_SIZE - 1)) != 0)
        return _EINVAL;
    return sys_mmap2(addr, (dword_t)len, prot, flags, fd_no,
                     (dword_t)(offset >> PAGE_BITS));
}

// Temporary link compatibility for entries inherited from the AArch64 syscall
// table. A real x86_64 statfs ABI conversion will replace these before dynamic
// userspace/BDS is considered supported.
dword_t sys_statfs_arm64(addr_t path_addr, addr_t buf_addr) {
    (void) path_addr;
    (void) buf_addr;
    return _ENOSYS;
}

dword_t sys_fstatfs_arm64(fd_t fd, addr_t buf_addr) {
    (void) fd;
    (void) buf_addr;
    return _ENOSYS;
}

// The direct x86_64 interpreter does not generate threaded-code fiber blocks.
// Keep the MMU-facing asbestos lifecycle hooks available so the shared memory
// subsystem can be reused unchanged during bring-up.
struct asbestos *asbestos_new(struct mmu *mmu) {
    struct asbestos *asbestos = calloc(1, sizeof(*asbestos));
    if (asbestos != NULL)
        asbestos->mmu = mmu;
    return asbestos;
}

void asbestos_free(struct asbestos *asbestos) {
    free(asbestos);
}

void asbestos_invalidate_range(struct asbestos *asbestos, page_t start, page_t end) {
    (void) asbestos;
    (void) start;
    (void) end;
}

void asbestos_invalidate_page(struct asbestos *asbestos, page_t page) {
    (void) asbestos;
    (void) page;
}

void asbestos_invalidate_all(struct asbestos *asbestos) {
    (void) asbestos;
}
