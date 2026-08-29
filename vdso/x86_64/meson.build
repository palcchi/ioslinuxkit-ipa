clang = find_program('/usr/local/opt/llvm/bin/clang', '/opt/homebrew/opt/llvm/bin/clang', '/opt/local/bin/clang', 'clang', required: false)

if clang.found()
    vdso_compiler = [clang, '-target', 'x86_64-linux-gnu', '-fuse-ld=lld']
    vdso = custom_target('vdso-x86_64',
        input: ['vdso.S', 'vdso.lds'],
        output: 'libvdso.so.elf',
        command: vdso_compiler + [
            '-o', '@OUTPUT@', '@INPUT0@',
            '-nostdlib', '-Wl,-T,@INPUT1@', '-Wl,--hash-style,sysv',
            '-shared', '-fPIC', '-ffreestanding'
        ] + get_option('vdso_c_args').split())
else
    message('x86_64 VDSO: clang not found, using empty placeholder')
    vdso = custom_target('vdso-x86_64-stub',
        output: 'libvdso.so.elf',
        command: ['touch', '@OUTPUT@'])
endif
