.text

.globl __kernel_rt_sigreturn
.type __kernel_rt_sigreturn,@function
__kernel_rt_sigreturn:
    mov $15, %rax
    syscall
    ud2
.size __kernel_rt_sigreturn, .-__kernel_rt_sigreturn

.globl __kernel_clock_gettime
.type __kernel_clock_gettime,@function
__kernel_clock_gettime:
    mov $228, %rax
    syscall
    ret
.size __kernel_clock_gettime, .-__kernel_clock_gettime

.globl __kernel_clock_getres
.type __kernel_clock_getres,@function
__kernel_clock_getres:
    mov $229, %rax
    syscall
    ret
.size __kernel_clock_getres, .-__kernel_clock_getres

.globl __kernel_gettimeofday
.type __kernel_gettimeofday,@function
__kernel_gettimeofday:
    mov $96, %rax
    syscall
    ret
.size __kernel_gettimeofday, .-__kernel_gettimeofday
