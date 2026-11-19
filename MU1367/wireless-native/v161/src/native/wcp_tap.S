/* SPDX-License-Identifier: GPL-3.0-or-later
 * ARM EABI: preserve the original vararg stack and callee-saved registers.
 * r12 is caller-scratch. The integer fprintf path has no VFP varargs in use.
 */
.syntax unified
.arm
.text
.align 2
.global fprintf
.type fprintf,%function
fprintf:
    push {r0-r12,lr}
    mov r0,sp
    bl wcp_tap_fprintf
    str r0,[sp,#48]
    pop {r0-r12,lr}
    bx r12
.size fprintf,.-fprintf
.global send
.type send,%function
send:
    push {r0-r12,lr}
    mov r0,sp
    bl wcp_tap_send
    str r0,[sp]
    pop {r0-r12,lr}
    bx lr
.size send,.-send
.global strlcpy
.type strlcpy,%function
strlcpy:
    push {r0-r12,lr}
    mov r0,sp
    bl wcp_tap_strlcpy
    str r0,[sp,#48]
    pop {r0-r12,lr}
    bx r12
.size strlcpy,.-strlcpy
.section .note.GNU-stack,"",%progbits
