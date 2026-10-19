/* SPDX-License-Identifier: GPL-3.0-or-later
 * B3: a bounded, read-only virtual-file handoff. No I/O/allocation/wait in
 * producer hooks. All addresses/PLT calls verified against the OEM MU1427 SO.
 * Protocol/identification handling remains the tested B2 implementation.
 */
.syntax unified
.arch armv7-a
.arm
.text
.equ POOL_SIZE, 0x8140
.equ ENTRY_SIZE, 0x88
.equ ENTRY_TAG, 0x3349
.equ MAGIC_LO, 0x4752
.equ MAGIC_HI, 0x3149

/* Find the LAST root entry, tagged by us. No scan, allocation or OS calls.
 * Return r0=pool, r1=entry, or r0=0. Uses caller-saved registers only.
 */
.global publication_find
publication_find:
    ldr r2, [r0, #0x118]
    cmp r2, #1
    blo find_missing
    cmp r2, #9
    bhi find_missing
    ldr r1, [r0, #0x114]
    cmp r1, #0
    beq find_missing
    sub r2, r2, #1
    add r2, r2, r2, lsl #4
    add r1, r1, r2, lsl #3
    ldr r2, [r1, #0x84]
    movw r3, #ENTRY_TAG
    cmp r2, r3
    bne find_missing
    ldr r0, [r1, #0x7c]
    bx lr
find_missing:
    mov r0, #0
    bx lr

/* Initialization runs before entries are exposed/receive processing starts.
 * Allocation failure leaves the stock driver working, with no new file.
 */
.global publication_init
publication_init:
    push {r4-r10, lr}
    mov r4, r0
    ldr r6, [r4, #0x118]
    cmp r6, #1
    blo init_done
    cmp r6, #8
    bhi init_done
    mov r0, #1
    movw r1, #POOL_SIZE
    bl native_calloc
    movs r5, r0
    beq init_done
    /* CLOCK_MONOTONIC=2 and 8-byte timespec verified at wait_for_state.
     * Distinguishes a new driver allocation/process from session-counter reuse.
     */
    mov r0, #2
    add r1, r5, #40
    bl native_clock_gettime
    cmp r0, #0
    bne init_free
    ldr r0, [r4, #0x114]
    add r1, r6, #1
    add r1, r1, r1, lsl #4
    lsl r1, r1, #3
    bl native_realloc
    movs r7, r0
    bne init_entry
init_free:
    mov r0, r5
    bl native_free
    b init_done
init_entry:
    str r7, [r4, #0x114]
    add r8, r6, r6, lsl #4
    add r8, r7, r8, lsl #3
    mov r0, r8
    mov r1, #0
    mov r2, #ENTRY_SIZE
    bl native_memset
    mov r0, r8
    movw r1, #0x8124             /* S_IFREG | 0444, stock EAP file mode */
    mov r2, #0
    mov r3, #0
    bl native_attr_init
    /* Use the same mount pointer as the original root entry, when present. */
    cmp r6, #0
    ldrne r0, [r7]
    strne r0, [r8]
    mov r0, #0
    str r0, [r8, #0x70]         /* ordinary named entry for stock readdir */
    str r6, [r8, #0x74]
    adr r0, publication_name
    str r0, [r8, #0x78]
    str r5, [r8, #0x7c]
    movw r0, #ENTRY_TAG
    str r0, [r8, #0x84]         /* unused extension word, not iofunc_attr */
    movw r0, #MAGIC_LO
    movt r0, #MAGIC_HI
    str r0, [r5]
    mov r0, #1
    str r0, [r5, #4]
    movw r0, #POOL_SIZE
    str r0, [r5, #8]
    dmb ish
    add r6, r6, #1
    str r6, [r4, #0x118]        /* expose only after complete initialization */
init_done:
    pop {r4-r10, pc}

/* Try once; NEVER spin or wait. Contention/loss is sticky until allocation
 * is destroyed (a new driver process). Reader must invalidate on fault != 0.
 * r0=pool; returns r0=1 with odd seqlock, or zero with sticky loss flag.
 */
publication_lock:
    add r2, r0, #32
    ldrex r1, [r2]
    cmp r1, #0
    bne lock_busy
    mov r3, #1
    strex r1, r3, [r2]
    cmp r1, #0
    bne lock_lost
    dmb ish
    ldr r1, [r0, #12]
    add r1, r1, #1
    str r1, [r0, #12]
    dmb ish
    mov r0, #1
    bx lr
lock_busy:
    clrex
lock_lost:
    mov r1, #1
    str r1, [r0, #28]
    mov r0, #0
    bx lr
publication_unlock:
    dmb ish
    ldr r1, [r0, #12]
    add r1, r1, #1
    str r1, [r0, #12]
    dmb ish
    mov r1, #0
    str r1, [r0, #32]
    bx lr

/* r0=driver, r1=enabled. Identification starts a new session. Teardown
 * disables publication and empties history. Old slot bytes are not zeroed;
 * count/session determine validity. Fault is deliberately NOT reset here.
 */
.global publication_control
publication_control:
    push {r4-r6, lr}
    mov r5, r1
    bl publication_find
    movs r4, r0
    beq control_done
    bl publication_lock
    cmp r0, #0
    beq control_done
    cmp r5, #0
    beq control_off
    ldr r0, [r4, #16]
    adds r0, r0, #1
    bne control_session
    mov r1, #1
    str r1, [r4, #28]
    mov r5, #0
control_session:
    str r0, [r4, #16]
control_off:
    str r5, [r4, #36]
    mov r0, #0
    str r0, [r4, #20]
    str r0, [r4, #24]
    mov r0, r4
    bl publication_unlock
control_done:
    pop {r4-r6, pc}

/* r0=driver, r1=TLVs, r2=length, r3=id. Maximum copied payload: 2048 bytes.
 * Fixed sixteen-slot overwrite history. There is no consumer-owned pointer.
 */
.global publication_enqueue
publication_enqueue:
    push {r4-r11, ip, lr}
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl publication_find
    movs r8, r0
    beq enqueue_done
    ldr r1, [r8, #36]
    cmp r1, #0
    beq enqueue_done
    cmp r6, #2048
    bhi enqueue_fault
    bl publication_lock
    cmp r0, #0
    beq enqueue_done
    /* Recheck after acquiring: teardown may have disabled the channel. */
    ldr r0, [r8, #36]
    cmp r0, #0
    beq enqueue_unlock
    ldr r9, [r8, #20]
    adds r9, r9, #1
    beq enqueue_wrap
    sub r10, r9, #1
    and r10, r10, #15
    add r11, r8, r10, lsl #11
    add r11, r11, r10, lsl #4
    add r11, r11, #64
    str r9, [r11]
    strh r7, [r11, #4]
    strh r6, [r11, #6]
    ldr r0, [r8, #16]
    str r0, [r11, #8]
    mov r0, #0
    str r0, [r11, #12]
    add r0, r11, #16
    mov r1, r5
    mov r2, r6
    bl native_memcpy
    str r9, [r8, #20]
    ldr r0, [r8, #24]
    cmp r0, #16
    addlo r0, r0, #1
    str r0, [r8, #24]
enqueue_unlock:
    mov r0, r8
    bl publication_unlock
enqueue_done:
    pop {r4-r11, ip, pc}
enqueue_wrap:
    mov r0, #1
    str r0, [r8, #28]
    mov r0, #0
    str r0, [r8, #36]
    str r0, [r8, #20]
    str r0, [r8, #24]
    b enqueue_unlock
enqueue_fault:
    mov r0, #1
    str r0, [r8, #28]
    b enqueue_done

/* Wrappers keep the original prologues/epilogues and B2 validation intact. */
.global publication_ident_hook
publication_ident_hook:
    push {r0-r3, ip, lr}
    mov r0, r6
    mov r1, #1
    bl publication_control
    pop {r0-r3, ip, lr}
    b b2_ident_hook

.global publication_receive_hook
publication_receive_hook:
    push {r0-r3, ip, lr}
    mov r0, r4
    add r1, r6, #6
    sub r2, r7, #6
    ldr r3, [sp, #8]            /* original r2 = low message-ID byte */
    add r3, r3, #0x5200
    bl publication_enqueue
    pop {r0-r3, ip, lr}
    add r8, r2, #0x5200         /* replaced B2 instruction */
    b b2_receive_resume

.global publication_init_hook
publication_init_hook:
    push {r0-r3, ip, lr}
    cmp r0, #0
    bne init_hook_done
    mov r0, r5
    bl publication_init
init_hook_done:
    pop {r0-r3, ip, lr}
    add sp, sp, #12             /* replaced stock epilogue instruction */
    b stock_fsys_init_return

.global publication_destroy_hook
publication_destroy_hook:
    push {r0-r3, ip, lr}
    mov r1, #0
    bl publication_control
    pop {r0-r3, ip, lr}
    push {r4, lr}              /* replaced stock prologue instruction */
    b stock_link_destroy_resume

/* Read executes on the existing resource-manager request thread. It copies
 * one whole snapshot using at most three seqlock attempts, then MsgReply.
 * Short buffers fail EINVAL; a second read on this open returns EOF. Use
 * dd bs=65536 count=1, reopen for each subsequent poll. No writer lock held.
 */
.global publication_read_hook
publication_read_hook:
    push {r0-r11, ip, lr}
    mov r5, r1                  /* ctp */
    mov r6, r2                  /* io_read_t */
    mov r7, r3                  /* OCB */
    bl publication_find
    cmp r0, #0
    beq read_stock
    ldr r2, [r7]
    cmp r2, r1
    bne read_stock
    mov r8, r0                  /* pool */
    mov r0, r5
    mov r1, r6
    mov r2, r7
    mov r3, #0
    bl native_read_verify
    cmp r0, #0
    bne read_return
    ldrb r0, [r6, #8]
    cmp r0, #0
    movne r0, #89               /* stock unsupported xtype result */
    bne read_return
    ldr r0, [r7, #0x80]
    cmp r0, #0
    bne read_eof
    ldr r0, [r6, #4]
    movw r1, #POOL_SIZE
    cmp r0, r1
    movlo r0, #22
    blo read_return
    mov r0, r1
    bl native_malloc
    movs r9, r0
    moveq r0, #12
    beq read_return
    mov r10, #3
read_attempt:
    ldr r11, [r8, #12]
    tst r11, #1
    bne read_retry
    dmb ish
    mov r0, r9
    mov r1, r8
    movw r2, #POOL_SIZE
    bl native_memcpy
    dmb ish
    ldr r0, [r8, #12]
    cmp r0, r11
    bne read_retry
    ldr r0, [r9, #32]
    cmp r0, #0
    beq read_reply
read_retry:
    subs r10, r10, #1
    bne read_attempt
    mov r0, r9
    bl native_free
    mov r0, #11                 /* EAGAIN, no waiting */
    b read_return
read_reply:
    ldr r0, [r5]
    movw r1, #POOL_SIZE
    mov r2, r9
    mov r3, r1
    bl native_reply
    mov r0, r9
    bl native_free
    mov r0, #1
    str r0, [r7, #0x80]
    mov r0, #0x80000000         /* stock _RESMGR_NOREPLY */
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
read_stock:
    pop {r0-r11, ip, lr}
    push {r4-r8, r10, r11, lr}  /* exact stock fsys_read prologue */
    b stock_fsys_read_resume

publication_name:
    .asciz "rgi-events"
.balign 4
