/* SPDX-License-Identifier: GPL-3.0-or-later
 * Exact MU1367 now-playing seams. Persist the 64-bit media identity before
 * stock PPS publication; bind each new artwork transfer to that identity.
 * No parsing loops, allocation, I/O or waiting in either receive hook.
 */
.global artwork_track_hook
artwork_track_hook:
    push {r0-r12, lr}
    mrs ip, apsr
    push {ip, lr}
    ldr r0, [sp, #116]       /* original sp+0x34: native context */
    mov r1, r5              /* eight BE bytes of persistent identifier */
    ldrb r2, [r4]
    ldrb r3, [r4, #1]
    orr r2, r3, r2, lsl #8
    cmp r2, #12
    bne track_return
    ldr r2, [sp, #104]       /* original sp+0x28: inner container end */
    add r3, r1, #8
    cmp r3, r2
    bhi track_return
    bl artwork_track
track_return:
    pop {ip, lr}
    msr APSR_nzcvq, ip
    pop {r0-r12, lr}
    ldrb r3, [r5]           /* exact displaced stock instruction */
    b stock_track_resume

.global artwork_track
artwork_track:
    push {r4-r8, lr}
    mov r5, r1
    bl artwork_find
    movs r4, r0
    beq track_done
    bl artwork_lock
    cmp r0, #0
    beq track_done
    ldrb r6, [r5]
    ldrb r0, [r5, #1]
    orr r6, r0, r6, lsl #8
    ldrb r0, [r5, #2]
    orr r6, r0, r6, lsl #8
    ldrb r0, [r5, #3]
    orr r6, r0, r6, lsl #8
    ldrb r7, [r5, #4]
    ldrb r0, [r5, #5]
    orr r7, r0, r7, lsl #8
    ldrb r0, [r5, #6]
    orr r7, r0, r7, lsl #8
    ldrb r0, [r5, #7]
    orr r7, r0, r7, lsl #8
    ldr r0, [r4, #88]
    cmp r0, r7
    ldreq r0, [r4, #92]
    cmpeq r0, r6
    movw r0, #MAILBOX
    sub r0, r4, r0
    ldr r8, [r0, #16]      /* B4 connection generation */
    ldreq r0, [r4, #84]
    cmpeq r0, r8
    beq track_keep
    mov r0, #0
    str r0, [r4, #20]
    str r0, [r4, #24]
    str r0, [r4, #44]
    str r0, [r4, #116]     /* new UID cannot inherit an old binding */
track_keep:
    str r8, [r4, #84]
    str r7, [r4, #88]
    str r6, [r4, #92]
    orrs r0, r6, r7
    movne r0, #1
    str r0, [r4, #96]      /* absent/zero identity disables output */
    dmb ish
    mov r0, #0
    str r0, [r4, #80]
track_done:
    pop {r4-r8, pc}

.global artwork_bind_hook
artwork_bind_hook:
    push {r0-r12, lr}
    mrs ip, apsr
    push {ip, lr}
    ldr r0, [sp, #116]
    ldrb r1, [r5]
    bl artwork_bind
    pop {ip, lr}
    msr APSR_nzcvq, ip
    pop {r0-r12, lr}
    ldr r0, [sp, #0x34]
    b stock_bind_resume

.global artwork_bind
artwork_bind:
    push {r4-r6, lr}
    mov r5, r1
    bl artwork_find
    movs r4, r0
    beq bind_done
    bl artwork_lock
    cmp r0, #0
    beq bind_done
    str r5, [r4, #100]
    ldr r0, [r4, #88]
    str r0, [r4, #104]
    ldr r0, [r4, #92]
    str r0, [r4, #108]
    ldr r0, [r4, #84]
    str r0, [r4, #112]
    ldr r0, [r4, #96]
    str r0, [r4, #116]
    dmb ish
    mov r0, #0
    str r0, [r4, #80]
bind_done:
    pop {r4-r6, pc}

/* Called while the completion seam holds the mailbox lock, r7=mailbox,
 * r5=current native transfer ID. Caller-saved registers only.
 */
artwork_stamp:
    mov r0, #0
    str r0, [r7, #44]
    str r5, [r7, #40]
    ldr r0, [r7, #116]
    cmp r0, #1
    bxne lr
    ldr r0, [r7, #100]
    cmp r0, r5
    bxne lr
    ldr r0, [r7, #84]
    ldr r1, [r7, #112]
    cmp r0, r1
    bxne lr
    movw r1, #MAILBOX
    sub r1, r7, r1
    ldr r1, [r1, #16]
    cmp r0, r1
    bxne lr
    ldr r0, [r7, #104]
    ldr r1, [r7, #88]
    cmp r0, r1
    bxne lr
    ldr r2, [r7, #108]
    ldr r3, [r7, #92]
    cmp r2, r3
    bxne lr
    str r0, [r7, #48]
    str r2, [r7, #52]
    mov r0, #1
    str r0, [r7, #44]
    bx lr
