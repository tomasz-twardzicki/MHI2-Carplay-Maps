/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "wcp_smoothing.h"
#include "wcp_timing.h"
#include "wcp_rg.h"
int main(void) {
    struct wcp_smoothing s;struct wcp_fingerprint a,b,c;struct wcp_rg rg;
    unsigned char mailbox[33120],tlv[]={0,6,0,0,0,1},bad[]={0,3,0,0};
    const unsigned char annex[]={0,0,0,1,9,0xf0,0,0,1,0x67,1,2,0,0,0,1,0x65,4,0,0,1,0x41,8,9,0,0};
    const unsigned char avcc[]={0,0,0,3,0x67,1,2,0,0,0,2,0x65,4,0,0,0,3,0x41,8,9};
    unsigned i;uint64_t last=0;
    wcp_smoothing_init(&s,150);
    for(i=0;i<100;i++) {
        uint64_t capture=1000000+(uint64_t)i*25000,arrival=capture+(i%8)*15000;
        uint64_t slot=wcp_smoothing_slot(&s,capture,arrival);
        assert(slot==capture+150000 && slot>last);last=slot;
    }
    assert(s.delay==150000);
    assert(wcp_smoothing_slot(&s,4000000,4200000)==4200000 && s.delay==160000);
    for(i=0;i<100;i++)wcp_smoothing_slot(&s,5000000+i*25000,5500000+i*25000);
    assert(s.delay==250000);
    wcp_smoothing_slot(&s,60000000,60000000);assert(s.delay>=s.base && s.delay<250000);
    wcp_smoothing_init(&s,150);wcp_smoothing_slot(&s,1000000,1200000);assert(s.delay==160000);
    wcp_smoothing_slot(&s,31200000,31200000);assert(s.delay==160000);
    wcp_smoothing_slot(&s,32200000,32200000);assert(s.delay==159000);
    wcp_smoothing_slot(&s,33200000,33200000);assert(s.delay==158000);
    wcp_smoothing_init(&s,0);assert(wcp_smoothing_slot(&s,1,9999)==9999 && s.delay==0);
    assert(wcp_fingerprint_annexb(&a,annex,sizeof(annex)));
    assert(wcp_fingerprint_avcc(&b,avcc,sizeof(avcc),4));assert(wcp_fingerprint_equal(&a,&b));
    assert(wcp_fingerprint_avcc(&c,avcc,sizeof(avcc)-1,4)==0);
    wcp_rg_init(&rg,123,42,1234);assert(!wcp_rg_message(&rg,0x5201,tlv,sizeof(tlv)));
    wcp_rg_accept(&rg,1);assert(!wcp_rg_message(&rg,0x5201,bad,sizeof(bad)));
    for(i=0;i<30;i++)assert(wcp_rg_message(&rg,i%3==0?0x5204:i%3==1?0x5202:0x5201,tlv,sizeof(tlv)));
    assert(rg.sequence==30 && wcp_rg_mailbox(&rg,mailbox,sizeof(mailbox))==448);
    assert(!memcmp(mailbox,"RGM1",4) && !memcmp(mailbox+32,"RGI1",4));
    assert(mailbox[96]==15 && mailbox[96+22*15]==30);
    wcp_rg_accept(&rg,0);assert(rg.sequence==0 && wcp_rg_mailbox(&rg,mailbox,sizeof(mailbox))==32 && mailbox[16]==2);
    wcp_rg_accept(&rg,1);assert(rg.session==2 && rg.sequence==0);
    {
        AltFrameRing *ring=calloc(1,sizeof(*ring));assert(ring);ring->write_sequence=5;
        for(i=1;i<=5;i++){ring->slots[i-1].committed_sequence=i;ring->slots[i-1].type=ALT_FRAME_TYPE_VIDEO;}
        assert(wcp_smoothing_newer_idr(ring,1)==0);
        ring->slots[2].flags=ring->slots[4].flags=ALT_FRAME_FLAG_KEYFRAME;
        assert(wcp_smoothing_newer_idr(ring,1)==5);
        ring->slots[3].type=ALT_FRAME_TYPE_CONFIG;assert(wcp_smoothing_newer_idr(ring,1)==3);
        ring->slots[1].committed_sequence=99;assert(wcp_smoothing_newer_idr(ring,1)==0);free(ring);
    }
    puts("WCP_POLICY_PASS steady_slots=100 adaptive_cap=250 decode_payload_identity=1 mailbox_wrap=1 session_clear=1");
    return 0;
}
