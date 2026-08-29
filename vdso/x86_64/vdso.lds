SECTIONS
{
    . = SIZEOF_HEADERS;
    .hash           : { *(.hash) } :text
    .gnu.hash       : { *(.gnu.hash) }
    .dynsym         : { *(.dynsym) }
    .dynstr         : { *(.dynstr) }
    .gnu.version    : { *(.gnu.version) }
    .gnu.version_d  : { *(.gnu.version_d) }
    .gnu.version_r  : { *(.gnu.version_r) }
    .dynamic        : { *(.dynamic) } :text :dynamic
    .rodata         : { *(.rodata*) } :text
    .note           : { *(.note*) } :text :note
    .eh_frame_hdr   : { *(.eh_frame_hdr) } :text :eh_frame_hdr
    .eh_frame       : { KEEP(*(.eh_frame)) } :text
    .text           : { *(.text*) } :text =0x90
    .data           : { *(.data*) *(.sdata*) *(.got.plt) *(.got) *(.bss*) } :text
    /DISCARD/       : { *(.note.GNU-stack) *(.interp) }
}

PHDRS
{
    text            PT_LOAD     FLAGS(5) FILEHDR PHDRS;
    dynamic         PT_DYNAMIC  FLAGS(4);
    note            PT_NOTE     FLAGS(4);
    eh_frame_hdr    PT_GNU_EH_FRAME;
}

VERSION
{
    LINUX_2.6 {
        global:
            __kernel_rt_sigreturn;
            __kernel_clock_gettime;
            __kernel_clock_getres;
            __kernel_gettimeofday;
        local: *;
    };
}
