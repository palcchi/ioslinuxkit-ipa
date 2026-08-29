#include <stdlib.h>
#include "asbestos/asbestos.h"

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
