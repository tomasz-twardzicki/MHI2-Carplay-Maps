/* SPDX-License-Identifier: GPL-3.0-or-later
 * MU1367 v1.5.0-e: the two run-time ABI conversions aa-most-feeder needs that neither the factory libc.so.3 nor the
 * pinned SDK image provides (no libgcc). Built only into the QNX binary (-mfpu=vfpv3-d16: the u32 <-> double
 * conversions below are single VFP instructions, so these never call themselves). Host builds use libgcc's.
 * Tested against the host compiler's conversions by tests/android-auto/test_aeabi_conv.c. */
#include <stdint.h>
#ifndef AEABI_PREFIX
#define AEABI_PREFIX(n) n
#endif
double AEABI_PREFIX(__aeabi_ul2d)(uint64_t v);
uint64_t AEABI_PREFIX(__aeabi_d2ulz)(double d);
/* hi * 2^32 is exact, so the sum is rounded once: the correctly rounded result. */
double AEABI_PREFIX(__aeabi_ul2d)(uint64_t v)
{
    return (double)(uint32_t)(v >> 32) * 4294967296.0 + (double)(uint32_t)v;
}
/* Truncation toward zero; NaN and values <= 0 give 0, values >= 2^64 saturate (as libgcc on these inputs). */
uint64_t AEABI_PREFIX(__aeabi_d2ulz)(double d)
{
    uint32_t hi;
    if (!(d > 0.0)) return 0u;
    if (d >= 18446744073709551616.0) return UINT64_MAX;
    hi = (uint32_t)(d / 4294967296.0);          /* division by a power of two is exact */
    return ((uint64_t)hi << 32) | (uint32_t)(d - (double)hi * 4294967296.0);
}
