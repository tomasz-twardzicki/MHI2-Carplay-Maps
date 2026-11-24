/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPMAP_WCP_RG_H
#define CPMAP_WCP_RG_H
#include <stdint.h>
#include <stddef.h>
#define WCP_RG_SLOTS 16
#define WCP_RG_MAX 2048
struct wcp_rg_event { uint32_t sequence; uint16_t id, size; unsigned char payload[WCP_RG_MAX]; };
struct wcp_rg {
    uint32_t session, sequence, serial, seconds, nanoseconds;
    uint64_t nonce;
    int accepted;
    struct wcp_rg_event events[WCP_RG_SLOTS];
};
void wcp_rg_init(struct wcp_rg *, uint64_t nonce, uint32_t seconds, uint32_t nanoseconds);
void wcp_rg_accept(struct wcp_rg *, int accepted);
int wcp_rg_message(struct wcp_rg *, unsigned id, const unsigned char *, size_t);
size_t wcp_rg_mailbox(struct wcp_rg *, unsigned char *, size_t);
#endif
