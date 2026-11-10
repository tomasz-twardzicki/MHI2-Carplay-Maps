/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host check of src/android-auto/feeder/aeabi_conv.c against the compiler's own conversions. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define AEABI_PREFIX(n) t##n
#include "../../src/android-auto/feeder/aeabi_conv.c"
static uint64_t x = 88172645463325252ull;
static uint64_t rnd(void) { x ^= x << 13; x ^= x >> 7; x ^= x << 17; return x; }
int main(void)
{
    unsigned long n = 0, bad = 0;
    int i, s;
    for (i = 0; i < 2000000; ++i) {
        uint64_t v = rnd() >> (rnd() % 64);
        double a = t__aeabi_ul2d(v), b = (double)v;
        n++; if (memcmp(&a, &b, sizeof a) != 0) { if (bad++ < 5) printf("ul2d %llu\n", (unsigned long long)v); }
        double d = b * (double)(rnd() % 1000 + 1) / 997.0;
        if (d < 18446744073709551616.0) { n++; if (t__aeabi_d2ulz(d) != (uint64_t)d) { if (bad++ < 5) printf("d2ulz %.17g\n", d); } }
    }
    for (s = 0; s < 64; ++s) {
        uint64_t e = 1ull << s; uint64_t vs[3] = { e - 1u, e, e + 1u }; int k;
        for (k = 0; k < 3; ++k) {
            double a = t__aeabi_ul2d(vs[k]), b = (double)vs[k];
            n++; if (memcmp(&a, &b, sizeof a)) bad++;
            if (b < 18446744073709551616.0) { n++; if (t__aeabi_d2ulz(b) != (uint64_t)b) bad++; }
        }
    }
    if (t__aeabi_d2ulz(-1.0) != 0 || t__aeabi_d2ulz(0.0) != 0 || t__aeabi_d2ulz(0.999) != 0 || t__aeabi_d2ulz(1e30) != UINT64_MAX) bad++;
    printf("AEABI_CONV checks=%lu bad=%lu\n", n + 4, bad);
    return bad != 0;
}
