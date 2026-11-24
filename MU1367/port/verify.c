/* Streaming SHA-256 file verifier; no optional on-unit hash commands needed.
 * SPDX-License-Identifier: GPL-3.0-or-later
 * FIPS 180-4 SHA-256 algorithm; standalone implementation.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static const uint32_t k[64] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
static uint32_t r(uint32_t a, unsigned n) { return (a >> n) | (a << (32-n)); }
static void block(uint32_t *h, const unsigned char *p) {
    uint32_t w[64], a,b,c,d,e,f,g,v,t,u; unsigned i;
    for(i=0;i<16;i++) w[i]=((uint32_t)p[i*4]<<24)|((uint32_t)p[i*4+1]<<16)|((uint32_t)p[i*4+2]<<8)|p[i*4+3];
    for(i=16;i<64;i++) w[i]=w[i-16]+(r(w[i-15],7)^r(w[i-15],18)^(w[i-15]>>3))+w[i-7]+(r(w[i-2],17)^r(w[i-2],19)^(w[i-2]>>10));
    a=h[0];b=h[1];c=h[2];d=h[3];e=h[4];f=h[5];g=h[6];v=h[7];
    for(i=0;i<64;i++) {
        t=v+(r(e,6)^r(e,11)^r(e,25))+((e&f)^((~e)&g))+k[i]+w[i];
        u=(r(a,2)^r(a,13)^r(a,22))+((a&b)^(a&c)^(b&c));
        v=g;g=f;f=e;e=d+t;d=c;c=b;b=a;a=t+u;
    }
    h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=v;
}
int main(int argc,char **argv) {
    uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    unsigned char buf[64]; char hex[65]; size_t n,i; uint64_t total=0; FILE *file; struct stat st;
    if(argc!=2 && argc!=3) return 2;
    if(stat(argv[1],&st) || !S_ISREG(st.st_mode)) return 2;
    file=fopen(argv[1],"rb"); if(!file) return 2;
    while((n=fread(buf,1,64,file))==64) { block(h,buf); total+=64; }
    if(ferror(file)) { fclose(file); return 2; }
    if(fclose(file)) return 2;
    total=(total+n)*8; buf[n++]=0x80;
    if(n>56) { memset(buf+n,0,64-n);block(h,buf);n=0; }
    memset(buf+n,0,56-n);
    for(i=0;i<8;i++) buf[63-i]=(unsigned char)(total>>(i*8));
    block(h,buf);
    for(i=0;i<8;i++) sprintf(hex+i*8,"%08lx",(unsigned long)h[i]);
    if(argc==3) return strlen(argv[2])==64 && strcmp(hex,argv[2])==0 ? 0 : 1;
    puts(hex);return 0;
}
