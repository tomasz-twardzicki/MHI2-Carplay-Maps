/* SPDX-License-Identifier: GPL-3.0-or-later
 * MU1427 B2: receive guidance before the stock unknown-ID rejection.
 * Protocol layout adapted from luka-dev/mib2q-carplay-rgi, rgd_tlv.c:
 * Copyright (c) 2026 LuKa (@LuKa_dev), GPL-3.0-or-later.
 * All addresses are resolved by patch-driver.py; no absolute runtime pointers.
 */
.syntax unified
.arch armv7-a
.arm
.text
.balign 4

/* Replaces mov r0,r6 at ident_info_request+0x8c, after ALL stock builders.
 * r6 = driver, r7 = packet. Failure uses the stock packet cleanup path.
 */
.global ident_hook
ident_hook:
    push {r4, lr}
    sub sp, sp, #8
    mov r0, r6
    mov r1, r7
    mov r2, #0x1e
    adr r3, .Lcomponent
    movw ip, :lower16:(component_end-component)
    str ip, [sp]
    bl packet_addparam_blob
    cmp r0, #0
    add sp, sp, #8
    pop {r4, lr}
    blt ident_failed
    mov r0, r6
    b ident_resume
ident_failed:
    mvn r5, #0
    b ident_cleanup

/* Replaces mov r0,r5 at the feature-start epilogue. Stock r5 is its return
 * code; r4 is the driver. Preserve that code even if the extra send fails.
 * The stock caller gates this function on (driver->flags & 3) == 3.
 * No global state: a new USB session gets its own feature-start invocation.
 */
.global start_hook
start_hook:
    push {r1-r3, r4, ip, lr}
    cmp r5, #0
    bne start_done
    mov r0, r4
    adr r1, .Lstart_frame
    movw r2, :lower16:(start_frame_end-start_frame)
    bl link_send_raw_message
    mov r3, r0
    ldr r0, [r4, #0x14]
    mov r1, #0
    adr r2, start_log
    bl driver_log
start_done:
    mov r0, r5
    pop {r1-r3, r4, ip, pc}

/* Replaces BL link_handle_reply at 0x133a0, BEFORE the message-table gate.
 * r0 = driver, r1 = packet. B1's later hook was never reached for unknown IDs.
 * Stock link_handle_reply returns positive EINVAL (22), which the transport
 * mistakes for a retained reply packet and does not recycle. B2 handles only
 * well-formed advertised 5201/5202/5204, returns zero, and leaves the stock
 * ACK/dispatch/receive-buffer recycling path intact. Others tail-call stock.
 */
.global receive_hook
receive_hook:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    ldr r6, [r5, #0x24]
    cmp r6, #0
    beq receive_fallback
    ldr r7, [r5, #0x1c]
    cmp r7, #16
    blo receive_fallback
    ldr r2, [r5, #0x20]
    cmp r7, r2
    bhi receive_fallback
    ldr r2, [r5, #0x18]
    add r2, r2, #9
    cmp r6, r2
    bne receive_fallback
    sub r7, r7, #10
    ldrh r2, [r5, #0x28]
    cmp r7, r2
    bne receive_fallback
    ldrb r2, [r6]
    cmp r2, #0x40
    bne receive_fallback
    ldrb r2, [r6, #1]
    cmp r2, #0x40
    bne receive_fallback
    ldrb r2, [r6, #2]
    ldrb r3, [r6, #3]
    orr r2, r3, r2, lsl #8
    cmp r7, r2
    bne receive_fallback
    ldrb r2, [r6, #4]
    cmp r2, #0x52
    bne receive_fallback
    ldrb r2, [r6, #5]
    cmp r2, #1
    beq receive_guidance
    cmp r2, #2
    beq receive_guidance
    cmp r2, #4
    bne receive_fallback
receive_guidance:
    add r8, r2, #0x5200
    sub r7, r7, #6
    sub sp, sp, #8
    str r7, [sp]
    ldr r0, [r4, #0x14]
    mov r1, #0
    adr r2, receive_log
    mov r3, r8
    bl driver_log
    add sp, sp, #8
    ldr r0, [r4, #0x14]
    add r1, r6, #6
    mov r2, r7
    bl driver_hexdump
    mov r0, #0
    pop {r4-r8, pc}
receive_fallback:
    mov r0, r4
    mov r1, r5
    pop {r4-r8, lr}
    b stock_link_handle_reply

.balign 4
.global component
component:
.Lcomponent:
    /* Nested big-endian TLVs. packet_addparam_blob adds the outer 0x001e. */
    .byte 0,6, 0,0, 0,0x10
    .byte 0, (.Lname_end-.Lname+4), 0,1
.Lname:
    .asciz "RouteGuidanceDisplayComponent"
.Lname_end:
    .byte 0,6, 0,2, 1,0
    .byte 0,6, 0,3, 1,0
    .byte 0,6, 0,4, 1,0
    .byte 0,6, 0,5, 1,0
    .byte 0,6, 0,6, 0,6
    .byte 0,6, 0,7, 1,0
    .byte 0,6, 0,8, 0,6
.global component_end
component_end:
.balign 4
.global start_frame
start_frame:
.Lstart_frame:
    /* Semantic iAP2 frame, not FF5A: stock send owns sequence/ACK/checksum. */
    .byte 0x40,0x40, 0,24, 0x52,0
    .byte 0,6, 0,0, 0,0x10
    .byte 0,4, 0,1
    .byte 0,4, 0,2
    .byte 0,4, 0,3
.global start_frame_end
start_frame_end:
start_log:
    .asciz "CPMAP_RGI_START B2 0x5200 rc=%d (0=queued)\n"
receive_log:
    .asciz "CPMAP_RGI_RX B2 id=0x%04x len=%u (TLVs follow)\n"
.balign 4
