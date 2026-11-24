/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPMAP_WCP_LOCATION_H
#define CPMAP_WCP_LOCATION_H
#include <stddef.h>
#include <stdint.h>
/* Protocol core only. No receiver hooks or source are installed by this file.
 * Caller serializes access, supplies CLOCK_MONOTONIC microseconds and resets
 * ownership on transport replacement, USB takeover, disable or source restart.
 */
#define WCP_LOCATION_MAX 128
#define WCP_LOCATION_AGE_US 1500000ULL
#define WCP_LOCATION_START 0xfffaU
#define WCP_LOCATION_DATA  0xfffbU
#define WCP_LOCATION_STOP  0xfffcU
struct wcp_location_slot {
    unsigned size, sequence, sent, utc;
    uint64_t received;
    char sentence[WCP_LOCATION_MAX+1];
};
struct wcp_location {
    uint64_t owner;
    unsigned requested, advertised;
    struct wcp_location_slot slot[2];
};
void wcp_location_reset(struct wcp_location *, uint64_t owner);
/* Raw OEM NMEA only: no timestamp synthesis, coordinate conversion or replay.
 * sequence must advance for the live source, even for invalid/no-fix input.
 * Returns 1 for a fresh valid fix, 0 for a rejected or no-fix sentence.
 */
int wcp_location_offer(struct wcp_location *, unsigned sequence, uint64_t captured,
                       uint64_t now, const char *, size_t);
/* Complete 0x4040 CSM IdentificationInformation. Transactional on failure.
 * Requires explicit enable AND fresh source; adds only GPGGA/GPRMC capability.
 */
int wcp_location_identify(struct wcp_location *, int enable, uint64_t now,
                          unsigned char *, size_t *size, size_t capacity);
int wcp_location_control(struct wcp_location *, unsigned id, const void *, size_t);
/* Complete CSM; caller must enqueue once on the current receiver's serialized
 * native control path. This function never touches a socket or native sequence.
 * accepted must describe the SAME owner passed to reset().
 */
size_t wcp_location_packet(struct wcp_location *, int accepted, uint64_t now,
                            unsigned char *, size_t capacity);
#endif
