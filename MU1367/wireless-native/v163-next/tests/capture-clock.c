#include <assert.h>
#include <stdio.h>
#include "wcp_capture_clock.h"
int main(void) {
    struct wcp_capture_clock c;uint64_t deadline,value,last,capture,arrival;unsigned i;
    memset(&c,0,sizeof(c));wcp_capture_clock_bind(&c,23,1);
    value=wcp_capture_clock_step(&c,10000000,12100000,&deadline);
    assert(value==10000000 && deadline==10000000);
    value=wcp_capture_clock_step(&c,0,12125000,&deadline);
    assert(value==10025000 && deadline==10025000);
    value=wcp_capture_clock_step(&c,10050000,12150000,&deadline);
    assert(value==10050000 && c.repairs==0 && c.fallbacks==1);
    /* Arrival stalls then recovers; neither transition gets a seconds-long
     * presentation step or a one-tick backward clamp. */
    last=value;value=wcp_capture_clock_step(&c,0,14250000,&deadline);
    assert(value-last==25000 && c.repairs==1);
    last=value;value=wcp_capture_clock_step(&c,10100000,12200000,&deadline);
    assert(value-last==25000 && c.repairs==2 && deadline==10100000);
    /* Duplicate and backward mapped capture timestamps need continuity too. */
    last=value;value=wcp_capture_clock_step(&c,10100000,12225000,&deadline);
    assert(value>last && value-last<=250000);
    last=value;value=wcp_capture_clock_step(&c,10000000,12250000,&deadline);
    assert(value>last && value-last<=250000);
    /* Real accepted-session changes discard the previous clock mapping. */
    wcp_capture_clock_bind(&c,23,2);assert(!c.last && !c.capture_anchor && c.epochs==2);
    value=wcp_capture_clock_step(&c,0,20000000,&deadline);assert(value==20000000 && !deadline);
    value=wcp_capture_clock_step(&c,17900000,20025000,&deadline);
    assert(value==20025000 && deadline==17900000);
    wcp_capture_clock_bind(&c,24,0);assert(!c.last && c.epochs==3);
    value=wcp_capture_clock_step(&c,0,1000000,&deadline);assert(value==1000000);
    wcp_capture_clock_bind(&c,24,7);assert(c.last==1000000 && c.session==7);
    for(i=1;i<100000;i+=137) {
        uint64_t raw=(uint64_t)i*1000000+123456;
        uint64_t converted=wcp_ntp_us(wcp_us_ntp(raw));
        assert(converted<=raw && raw-converted<=1);
    }
    wcp_capture_clock_clear(&c);wcp_capture_clock_bind(&c,25,1);
    capture=10000000;arrival=12100000;last=0;
    for(i=0;i<50000;i++) {
        unsigned miss=i%13<3;
        capture+=25000;arrival+=25000;
        /* A large frame/reordered arrival creates isolated and consecutive
         * correlation misses, followed by a good clock anchor again. */
        value=wcp_capture_clock_step(&c,miss?0:capture,
            arrival+(i%100==1?2100000:0),&deadline);
        if(last)assert(value>last && value-last<=250000);
        last=value;
    }
    printf("CAPTURE_CLOCK_PASS simulated_frames=50000 fallbacks=%lu repairs=%lu\n",c.fallbacks,c.repairs);
    return 0;
}
