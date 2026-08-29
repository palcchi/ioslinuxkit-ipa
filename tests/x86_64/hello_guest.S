.section .text
.global _start
.type _start,@function
_start:
    mov $1, %eax
    mov $1, %edi
    lea message(%rip), %rsi
    mov $(message_end-message), %edx
    syscall

    mov $60, %eax
    xor %edi, %edi
    syscall
.size _start, .-_start

.section .rodata
message:
    .ascii "HELLO X86_64 GUEST\n"
message_end:
