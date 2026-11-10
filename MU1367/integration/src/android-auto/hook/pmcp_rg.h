/* SPDX-License-Identifier: GPL-3.0-or-later
 * pmcp (AA gamma): Android Auto navigation -> rg RAM mailbox (see pmcp_rg.c). */
#ifndef PMCP_RG_H
#define PMCP_RG_H
#define PMCP_RG_HIDDEN __attribute__((visibility("hidden")))
/* msg: one NavigationStatus message with its two-byte id, before nav_translate rewrites it. Any thread. */
PMCP_RG_HIDDEN void pmcp_rg_message(const unsigned char *msg, unsigned len);
/* 1.7 NavigationType -> iAP2 manoeuvre (exposed for the host test). 1 recognised, 0 not. */
PMCP_RG_HIDDEN int pmcp_rg_map(unsigned nt, unsigned exit_no, unsigned angle, int *t, int *j, int *side, int *a, int *has_a);
#endif
