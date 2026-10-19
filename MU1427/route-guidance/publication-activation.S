/* SPDX-License-Identifier: GPL-3.0-or-later
 * B4: native fsys_init_entries runs during iap2_start_features, AFTER identify.
 * Enable the newly allocated pool here, before B2's separate 5200 submission.
 */
.syntax unified
.arch armv7-a
.arm
.text
.global activation_init_hook
activation_init_hook:
    push {r0-r3, ip, lr}
    cmp r0, #0
    bne activation_done
    mov r0, r5
    bl b3_publication_init
    mov r0, r5
    mov r1, #1
    bl b3_publication_control
activation_done:
    pop {r0-r3, ip, lr}
    add sp, sp, #12
    b stock_fsys_init_return
