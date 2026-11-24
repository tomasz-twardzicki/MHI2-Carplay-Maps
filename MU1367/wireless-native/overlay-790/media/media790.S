/* SPDX-License-Identifier: GPL-3.0-or-later
 * Preserve the receiver's complete vararg stack and ARM register contract.
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
.global memcpy
.type memcpy,%function
memcpy:
    push {r0-r12,lr}
    mov r0,sp
    bl wcp_tap_memcpy
    str r0,[sp,#48]
    pop {r0-r12,lr}
    bx r12
.size memcpy,.-memcpy
.section .note.GNU-stack,"",%progbits
