/* SPDX-License-Identifier: GPL-3.0-or-later
 * N2 counters only. No artwork copies, allocation, I/O or waiting on receive.
 * The B4 ring, header and ordinary read path remain unchanged.
 */
.syntax unified
.arch armv7-a
.arm
.text
.equ EXT, 0x8140

/* r0 driver, r1 file ID, r2 event (0 association,1 setup,2 data),
 * r3 state before data. Native callers serialize transfer mutation.
 * A separate try-lock/seqlock protects only these diagnostic counters.
 */
.global artwork_note
artwork_note:
    push {r4-r10, lr}
    cmp r1, #255
    bhi note_done
    mov r4, r0
    mov r5, r2
    mov r6, r3
    add r7, r1, r1, lsl #1
    add r7, r4, r7, lsl #4
    ldrb r0, [r7, #0x120]
    cmp r0, #1
    bne note_done
    mov r0, r4
    bl b4_find
    cmp r0, #0
    beq note_done
    movw r1, #EXT
    add r8, r0, r1
    add r2, r8, #80
    ldrex r0, [r2]
    cmp r0, #0
    bne note_busy
    mov r1, #1
    strex r0, r1, [r2]
    cmp r0, #0
    bne note_lost
    dmb ish
    ldr r0, [r8, #12]
    add r0, r0, #1
    str r0, [r8, #12]
    dmb ish
    cmp r5, #0
    moveq r9, #20
    beq note_increment
    cmp r5, #1
    bne note_data
    ldr r0, [r8, #24]
    add r0, r0, #1
    str r0, [r8, #24]
    ldr r0, [r7, #0x128]
    ldr r1, [r7, #0x12c]
    str r0, [r8, #56]
    cmp r1, #0
    bne note_large
    movw r1, #0x3500
    movt r1, #0x000c          /* 800000 */
    cmp r0, r1
    bhi note_large
    ldrb r0, [r7, #0x121]
    cmp r0, #2
    moveq r9, #0
    movne r9, #48            /* setup did not leave receiving state */
    b note_increment
note_large:
    mov r9, #44
    b note_increment
note_data:
    ldr r0, [r8, #28]
    add r0, r0, #1
    str r0, [r8, #28]
    cmp r6, #2
    bne note_unlock
    ldrb r0, [r7, #0x121]
    cmp r0, #3
    bne note_unlock
    ldr r0, [r8, #32]
    add r0, r0, #1
    str r0, [r8, #32]
    ldr r0, [r7, #0x128]
    ldr r1, [r7, #0x12c]
    str r0, [r8, #56]
    cmp r1, #0
    bne note_unlock
    cmp r0, #8
    blo note_unlock
    movw r1, #0x3500
    movt r1, #0x000c
    cmp r0, r1
    bhi note_unlock
    ldr r1, [r7, #0x130]
    cmp r1, #0
    beq note_unlock
    ldrb r0, [r1]
    cmp r0, #255
    bne note_png
    ldrb r0, [r1, #1]
    cmp r0, #216
    bne note_png
    ldrb r0, [r1, #2]
    cmp r0, #255
    moveq r9, #36
    beq note_increment
note_png:
    /* Byte loads avoid assumptions about the stock buffer alignment. */
    adr r2, png_signature
    mov r3, #0
note_png_byte:
    ldrb r0, [r1, r3]
    ldrb r4, [r2, r3]
    cmp r0, r4
    movne r9, #52
    bne note_increment
    add r3, r3, #1
    cmp r3, #8
    blo note_png_byte
    mov r9, #40
note_increment:
    cmp r9, #0
    beq note_unlock
    ldr r0, [r8, r9]
    adds r0, r0, #1
    str r0, [r8, r9]
    movcs r0, #1
    strcs r0, [r8, #16]      /* sticky counter wrap */
note_unlock:
    dmb ish
    ldr r0, [r8, #12]
    add r0, r0, #1
    str r0, [r8, #12]
    dmb ish
    mov r0, #0
    str r0, [r8, #80]
note_done:
    pop {r4-r10, pc}
note_busy:
    clrex
note_lost:
    mov r0, #1
    str r0, [r8, #16]
    b note_done

/* Function-entry wrappers replay the exact displaced prologue, execute the
 * complete stock function, then observe without changing its return value.
 */
.macro wrapper name, event, resume, prologue
.global \name
\name:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, #0
    .if \event == 2
    add r6, r1, r1, lsl #1
    add r6, r0, r6, lsl #4
    ldrb r6, [r6, #0x121]
    .endif
    bl .Lstock_\name
    mov r8, r0
    mov r0, r4
    mov r1, r5
    mov r2, #\event
    mov r3, r6
    bl artwork_note
    mov r0, r8
    pop {r4-r8, pc}
.Lstock_\name:
    .word \prologue
    b \resume
.endm
wrapper artwork_init_hook, 0, stock_init_resume, 0xe92d41f0
wrapper artwork_setup_hook, 1, stock_setup_resume, 0xe92d4ff0
wrapper artwork_data_hook, 2, stock_data_resume, 0xe92d4ff0

/* 128-byte read is N2 diagnostics; every other request tail-calls B4.
 * Work/allocations here are on the stock resource-manager request thread.
 */
.global artwork_read_hook
artwork_read_hook:
    push {r0-r11, ip, lr}
    ldr r4, [r2, #4]
    cmp r4, #128
    bne read_b4
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl b4_find
    cmp r0, #0
    beq read_b4
    ldr r2, [r7]
    cmp r2, r1
    bne read_b4
    mov r8, r0
    mov r0, r5
    mov r1, r6
    mov r2, r7
    mov r3, #0
    bl native_read_verify
    cmp r0, #0
    bne read_return
    ldrb r0, [r6, #8]
    cmp r0, #0
    movne r0, #89
    bne read_return
    ldr r0, [r7, #0x80]
    cmp r0, #0
    bne read_eof
    mov r0, #128
    bl native_malloc
    movs r9, r0
    moveq r0, #12
    beq read_return
    movw r1, #EXT
    add r10, r8, r1
    mov r4, #3
read_attempt:
    ldr r11, [r10, #12]
    tst r11, #1
    bne read_retry
    dmb ish
    mov r0, r9
    mov r1, r10
    mov r2, #128
    bl native_memcpy
    dmb ish
    ldr r0, [r10, #12]
    cmp r0, r11
    bne read_retry
    ldr r0, [r9, #80]
    cmp r0, #0
    beq read_reply
read_retry:
    subs r4, r4, #1
    bne read_attempt
    mov r0, r9
    bl native_free
    mov r0, #11
    b read_return
read_reply:
    movw r0, #0x324e
    movt r0, #0x4f41         /* N2AO */
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
    ldr r0, [r5]
    mov r1, #128
    mov r2, r9
    mov r3, #128
    bl native_reply
    mov r0, r9
    bl native_free
    mov r0, #1
    str r0, [r7, #0x80]
    mov r0, #0x80000000
    b read_return
read_eof:
    ldr r0, [r5]
    mov r1, #0
    mov r2, #0
    mov r3, #0
    bl native_reply
    mov r0, #0x80000000
read_return:
    str r0, [sp]
    pop {r0-r11, ip, pc}
read_b4:
    pop {r0-r11, ip, lr}
    b b4_read
png_signature:
    .byte 137,80,78,71,13,10,26,10
.balign 4
