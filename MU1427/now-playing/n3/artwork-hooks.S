/* SPDX-License-Identifier: GPL-3.0-or-later
 * N3 owned, bounded diagnostic image mailbox. No decoder, I/O, allocation
 * or waiting in transfer hooks. Never consume the stock artwork cursor.
 */
.syntax unified
.arch armv7-a
.arm
.text
.equ MAILBOX, 0x81c0
.equ MAX_IMAGE, 800000
.equ REQUEST, 800128

/* Replace N2's size instruction, preserving the original calloc call. */
.global artwork_allocation
artwork_allocation:
    movw r1, #0xb740
    movt r1, #0x000c         /* B4 + N2 + 128 + 800000 = 833344 */
    b allocation_resume

/* r0=context -> r0=mailbox or zero; caller-saved registers only. */
artwork_find:
    push {r4, lr}
    bl b4_find
    cmp r0, #0
    movwne r1, #MAILBOX
    addne r0, r0, r1
    pop {r4, pc}

/* r0=mailbox. One exclusive attempt; never spin on receive. Contention is
 * sticky and disables image reads for this allocation. OEM work continues.
 */
artwork_lock:
    add r1, r0, #80
    ldrex r2, [r1]
    cmp r2, #0
    bne lock_busy
    mov r2, #1
    strex r3, r2, [r1]
    cmp r3, #0
    bne lock_fault
    dmb ish
    mov r0, #1
    bx lr
lock_busy:
    clrex
lock_fault:
    mov r2, #1
    str r2, [r0, #16]
    mov r0, #0
    bx lr

/* r0=context r1=id. Invalidate before stock destruction/setup can free or
 * replace a kind-1 image. Generation wrap is sticky/fail-closed.
 */
.global artwork_invalidate
artwork_invalidate:
    push {r4-r6, lr}
    cmp r1, #255
    bhi invalidate_done
    add r2, r1, r1, lsl #1
    add r2, r0, r2, lsl #4
    ldrb r2, [r2, #0x120]
    cmp r2, #1
    bne invalidate_done
    bl artwork_find
    movs r4, r0
    beq invalidate_done
    bl artwork_lock
    cmp r0, #0
    beq invalidate_done
    ldr r0, [r4, #12]
    adds r0, r0, #1
    str r0, [r4, #12]
    movcs r1, #1
    strcs r1, [r4, #16]
    mov r0, #0
    str r0, [r4, #20]       /* empty, no usable image */
    str r0, [r4, #24]
    dmb ish
    str r0, [r4, #80]
invalidate_done:
    pop {r4-r6, pc}

.global artwork_destroy_hook
artwork_destroy_hook:
    push {r0-r3, ip, lr}
    bl artwork_invalidate
    pop {r0-r3, ip, lr}
    .word 0xe92d4070        /* displaced stock push {r4-r6,lr} */
    b stock_destroy_resume

.global artwork_setup_hook_n3
artwork_setup_hook_n3:
    push {r0-r3, ip, lr}
    bl artwork_invalidate
    pop {r0-r3, ip, lr}
    b n2_setup

/* Exact complete-state seam: r6=context, r7=id. Copy BEFORE PPS can expose
 * completion to a consuming reader; stock data mutation owns this buffer.
 * Every register and the displaced mov are preserved for the stock code.
 */
.global artwork_complete_hook
artwork_complete_hook:
    push {r0-r12, lr}
    mov r0, r6
    mov r1, r7
    bl artwork_capture
    pop {r0-r12, lr}
    mov r3, #0
    b stock_complete_resume

.global artwork_capture
artwork_capture:
    push {r4-r10, lr}
    mov r4, r0
    mov r5, r1
    cmp r1, #255
    bhi capture_done
    ldr r2, [r4, #0xbc]
    cmp r2, r5
    bne capture_done        /* only the current native artwork slot */
    add r6, r1, r1, lsl #1
    add r6, r4, r6, lsl #4
    ldrb r2, [r6, #0x120]
    cmp r2, #1
    bne capture_done
    ldrb r2, [r6, #0x121]
    cmp r2, #3
    bne capture_done
    bl artwork_find
    movs r7, r0
    beq capture_done
    bl artwork_lock
    cmp r0, #0
    beq capture_done
    ldr r0, [r7, #12]
    adds r0, r0, #1
    str r0, [r7, #12]
    movcs r0, #1
    strcs r0, [r7, #16]
    mov r0, #0
    str r0, [r7, #20]
    str r0, [r7, #24]
    ldr r0, [r7, #16]
    cmp r0, #0
    bne capture_unlock
    ldr r8, [r6, #0x128]
    ldr r0, [r6, #0x12c]
    cmp r0, #0
    bne capture_reject
    cmp r8, #8
    blo capture_reject
    movw r0, #0x3500
    movt r0, #0x000c
    cmp r8, r0
    bhi capture_reject
    ldr r0, [r6, #0x140]
    cmp r0, r8
    bne capture_reject
    ldr r0, [r6, #0x144]
    cmp r0, #0
    bne capture_reject
    ldr r9, [r6, #0x130]
    cmp r9, #0
    beq capture_reject
    ldrb r0, [r9]
    cmp r0, #255
    bne capture_png
    ldrb r0, [r9, #1]
    cmp r0, #216
    bne capture_png
    ldrb r0, [r9, #2]
    cmp r0, #255
    moveq r10, #2           /* JPEG */
    beq capture_copy
capture_png:
    adr r1, png_signature_n3
    mov r2, #0
capture_png_byte:
    ldrb r0, [r9, r2]
    ldrb r3, [r1, r2]
    cmp r0, r3
    bne capture_reject
    add r2, r2, #1
    cmp r2, #8
    blo capture_png_byte
    mov r10, #1            /* PNG */
capture_copy:
    add r0, r7, #128
    mov r1, r9
    mov r2, r8
    bl native_memcpy
    str r8, [r7, #20]
    str r10, [r7, #24]
    movw r0, #MAILBOX
    sub r0, r7, r0
    ldr r0, [r0, #16]
    str r0, [r7, #36]       /* session at capture, not at later read */
    ldr r0, [r7, #28]
    adds r0, r0, #1
    str r0, [r7, #28]
    movcs r0, #1
    strcs r0, [r7, #16]
    b capture_unlock
capture_reject:
    ldr r0, [r7, #32]
    adds r0, r0, #1
    str r0, [r7, #32]
    movcs r0, #1
    strcs r0, [r7, #16]
capture_unlock:
    dmb ish
    mov r0, #0
    str r0, [r7, #80]
capture_done:
    pop {r4-r10, pc}

/* One large read selects the owned N3 mailbox. Every other request goes
 * through the A2-tested N2/B4 read path. Allocation/MsgReply are off RX.
 */
.global artwork_read_hook_n3
artwork_read_hook_n3:
    push {r0-r11, ip, lr}
    movw r4, #0x3580
    movt r4, #0x000c        /* 800128 */
    ldr r5, [r2, #4]
    cmp r4, r5
    bne read_fallback_n3
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl b4_find
    cmp r0, #0
    beq read_fallback_n3
    ldr r2, [r7]
    cmp r2, r1
    bne read_fallback_n3
    mov r8, r0
    mov r0, r5
    mov r1, r6
    mov r2, r7
    mov r3, #0
    bl native_read_verify
    cmp r0, #0
    bne read_return_n3
    ldrb r0, [r6, #8]
    cmp r0, #0
    movne r0, #89
    bne read_return_n3
    ldr r0, [r7, #0x80]
    cmp r0, #0
    bne read_eof_n3
    mov r0, r4
    bl native_malloc
    movs r9, r0
    moveq r0, #12
    beq read_return_n3
    movw r0, #MAILBOX
    add r10, r8, r0
    mov r0, r10
    bl artwork_lock
    cmp r0, #0
    beq read_busy_n3
    ldr r0, [r10, #16]
    cmp r0, #0
    bne read_fault_n3
    ldr r11, [r10, #20]
    ldr r0, [r8, #16]
    ldr r1, [r10, #36]
    cmp r0, r1
    movne r11, #0
    ldr r0, [r8, #36]
    cmp r0, #1
    movne r11, #0
    movw r0, #0x3500
    movt r0, #0x000c
    cmp r11, r0
    bhi read_fault_n3
    add r11, r11, #128
    mov r0, r9
    mov r1, r10
    mov r2, r11
    bl native_memcpy
    cmp r11, #128
    moveq r0, #0
    streq r0, [r9, #20]
    streq r0, [r9, #24]
    dmb ish
    mov r0, #0
    str r0, [r10, #80]
    ldr r0, [r10, #16]      /* RX contention while copying => reject */
    cmp r0, #0
    bne read_busy_n3
    movw r0, #0x334e
    movt r0, #0x5241        /* N3AR */
    str r0, [r9]
    mov r0, #1
    str r0, [r9, #4]
    mov r0, #128
    str r0, [r9, #8]
    ldr r0, [r8, #16]
    str r0, [r9, #64]
    ldr r0, [r8, #36]
    str r0, [r9, #68]
    ldr r0, [r8, #40]
    str r0, [r9, #72]
    ldr r0, [r8, #44]
    str r0, [r9, #76]
    mov r0, #0
    str r0, [r9, #80]
    ldr r0, [r5]
    mov r1, r11
    mov r2, r9
    mov r3, r11
    bl native_reply
    mov r0, r9
    bl native_free
    mov r0, #1
    str r0, [r7, #0x80]
    mov r0, #0x80000000
    b read_return_n3
read_fault_n3:
    dmb ish
    mov r0, #0
    str r0, [r10, #80]
read_busy_n3:
    mov r0, r9
    bl native_free
    mov r0, #11
    b read_return_n3
read_eof_n3:
    ldr r0, [r5]
    mov r1, #0
    mov r2, #0
    mov r3, #0
    bl native_reply
    mov r0, #0x80000000
read_return_n3:
    str r0, [sp]
    pop {r0-r11, ip, pc}
read_fallback_n3:
    pop {r0-r11, ip, lr}
    b n2_read
png_signature_n3:
    .byte 137,80,78,71,13,10,26,10
.balign 4
