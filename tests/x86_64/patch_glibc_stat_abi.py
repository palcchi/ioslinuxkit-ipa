from pathlib import Path

p = Path("fs/stat.c")
s = p.read_text()

anchor = '''struct stat_arm64 stat_convert_arm64(struct statbuf stat) {
'''
pos = s.find(anchor)
if pos < 0:
    raise SystemExit("stat_convert_arm64 anchor not found")
# Insert x86 definition before ARM64 conversion.
x86 = r'''// Native Linux x86_64 stat layout (144 bytes).  Reusing the ARM64
// 128-byte layout corrupts glibc's loader view even though the underlying
// filesystem metadata is correct.
struct stat_x86_64 {
    uint64_t dev;
    uint64_t ino;
    uint64_t nlink;
    uint32_t mode;
    uint32_t uid;
    uint32_t gid;
    uint32_t __pad0;
    uint64_t rdev;
    int64_t size;
    int64_t blksize;
    int64_t blocks;
    int64_t atime_;
    uint64_t atime_nsec;
    int64_t mtime_;
    uint64_t mtime_nsec;
    int64_t ctime_;
    uint64_t ctime_nsec;
    int64_t reserved[3];
};

static struct stat_x86_64 stat_convert_x86_64(struct statbuf stat) {
    struct stat_x86_64 out = {};
    out.dev = stat.dev;
    out.ino = stat.inode;
    out.nlink = stat.nlink;
    out.mode = stat.mode;
    out.uid = stat.uid;
    out.gid = stat.gid;
    out.rdev = stat.rdev;
    out.size = stat.size;
    out.blksize = stat.blksize;
    out.blocks = stat.blocks;
    out.atime_ = stat.atime;
    out.atime_nsec = stat.atime_nsec;
    out.mtime_ = stat.mtime;
    out.mtime_nsec = stat.mtime_nsec;
    out.ctime_ = stat.ctime;
    out.ctime_nsec = stat.ctime_nsec;
    return out;
}

static int put_guest_stat(addr_t addr, struct statbuf stat) {
#if defined(GUEST_X86_64)
    struct stat_x86_64 out = stat_convert_x86_64(stat);
    return user_put(addr, out) ? _EFAULT : 0;
#else
    struct stat_arm64 out = stat_convert_arm64(stat);
    return user_put(addr, out) ? _EFAULT : 0;
#endif
}

'''
s = s[:pos] + x86 + s[pos:]

old = '''    struct stat_arm64 arm64stat = stat_convert_arm64(stat);
    if (user_put(statbuf_addr, arm64stat))
        return _EFAULT;
    return 0;
}

dword_t sys_stat64'''
new = '''    return put_guest_stat(statbuf_addr, stat);
}

dword_t sys_stat64'''
if old not in s:
    raise SystemExit("sys_stat_path output block not found")
s = s.replace(old, new, 1)

old = '''dword_t sys_fstatat64(fd_t at, addr_t path_addr, addr_t statbuf_addr, dword_t flags) {
    return sys_stat_path(at, path_addr, statbuf_addr, !(flags & AT_SYMLINK_NOFOLLOW_));
}
'''
new = '''dword_t sys_fstatat64(fd_t at, addr_t path_addr, addr_t statbuf_addr, dword_t flags) {
    // glibc commonly implements fstat(fd) as newfstatat(fd, "", ..., AT_EMPTY_PATH).
    // Linux accepts that form, so do the fd lookup directly instead of trying to
    // normalize an empty pathname (which would otherwise return ENOENT).
    if (flags & AT_EMPTY_PATH_) {
        char path[MAX_PATH];
        if (user_read_string(path_addr, path, sizeof(path)))
            return _EFAULT;
        if (path[0] == '\\0') {
            struct fd *fd = at_fd(at);
            if (fd == NULL)
                return _EBADF;
            struct statbuf stat = {};
            int err = fd->mount->fs->fstat(fd, &stat);
            if (err < 0)
                return err;
            return put_guest_stat(statbuf_addr, stat);
        }
    }
    return sys_stat_path(at, path_addr, statbuf_addr, !(flags & AT_SYMLINK_NOFOLLOW_));
}
'''
if old not in s:
    raise SystemExit("sys_fstatat64 block not found")
s = s.replace(old, new, 1)

old = '''    struct stat_arm64 arm64stat = stat_convert_arm64(stat);
    if (user_put(statbuf_addr, arm64stat))
        return _EFAULT;
    return 0;
}

dword_t sys_statx'''
new = '''    return put_guest_stat(statbuf_addr, stat);
}

dword_t sys_statx'''
if old not in s:
    raise SystemExit("sys_fstat64 output block not found")
s = s.replace(old, new, 1)

p.write_text(s)
print("patched fs/stat.c with x86_64 stat ABI and AT_EMPTY_PATH")
