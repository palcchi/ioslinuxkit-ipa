#include <sys/utsname.h>
#include <stdint.h>
#include <stdatomic.h>
#include <string.h>
#include "kernel/calls.h"
#include "platform/platform.h"

#define SYSINFO_DEBUG 0

const char *uname_version = "Block Emulation";
const char *uname_hostname_override = NULL;

void do_uname(struct uname *uts) {
    struct utsname real_uname;
    uname(&real_uname);
    const char *hostname = real_uname.nodename;
    if (uname_hostname_override)
        hostname = uname_hostname_override;

    memset(uts, 0, sizeof(struct uname));
    strcpy(uts->system, "Linux");
    snprintf(uts->hostname, sizeof(uts->hostname), "%s", hostname);
    strcpy(uts->release, "4.20.69-linuxkit");
    snprintf(uts->version, sizeof(uts->version), "%s %s %s", uname_version, __DATE__, __TIME__);
#ifdef GUEST_X86_64
    strcpy(uts->arch, "x86_64");
#else
    strcpy(uts->arch, "aarch64");
#endif
    strcpy(uts->domain, "(none)");
}

dword_t sys_uname(addr_t uts_addr) {
    struct uname uts;
    do_uname(&uts);
    if (user_put(uts_addr, uts))
        return _EFAULT;
    return 0;
}

dword_t sys_sethostname(addr_t UNUSED(hostname_addr), dword_t UNUSED(hostname_len)) {
    return _EPERM;
}

static void sysinfo_specific(struct sys_info *info) {
    struct platform_sysinfo host_info = platform_get_sysinfo();
    uint64_t host_mem_unit = host_info.mem_unit ? host_info.mem_unit : 1;
    info->procs = host_info.procs;

#define GUEST_MAX_RAM (4ULL * 1024 * 1024 * 1024)
    uint64_t total_bytes = host_info.totalram * host_mem_unit;
    if (total_bytes > GUEST_MAX_RAM)
        total_bytes = GUEST_MAX_RAM;
    info->totalram = total_bytes;
    info->sharedram = host_info.sharedram * host_mem_unit;
    info->totalswap = host_info.totalswap * host_mem_unit;
    info->freeswap = host_info.freeswap * host_mem_unit;
    info->totalhigh = host_info.totalhigh * host_mem_unit;
    info->freehigh = host_info.freehigh * host_mem_unit;
    info->mem_unit = 1;

#if ANON_MMAP_LIMIT_PAGES > 0
    extern _Atomic long anon_page_count;
    long used_pages = atomic_load(&anon_page_count);
    uint64_t used_bytes = (uint64_t)(used_pages > 0 ? used_pages : 0) * 4096;
    info->freeram = used_bytes < total_bytes ? total_bytes - used_bytes : 0;
#else
    info->freeram = total_bytes / 2;
#endif
}

dword_t sys_sysinfo(addr_t info_addr) {
    struct sys_info info = {0};
    struct uptime_info uptime = get_uptime();
    info.uptime = uptime.uptime_ticks;
    info.loads[0] = uptime.load_1m;
    info.loads[1] = uptime.load_5m;
    info.loads[2] = uptime.load_15m;
    sysinfo_specific(&info);

    uint64_t existing_value = 0;
    if (user_get(info_addr, existing_value) == 0) {
        if (existing_value != 0 && (existing_value & 0xFF) == 0) {
            if (user_write(info_addr + 8, ((char*)&info) + 8, sizeof(info) - 8))
                return _EFAULT;
            return 0;
        }
    }

    if (user_put(info_addr, info))
        return _EFAULT;
    return 0;
}
