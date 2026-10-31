/* SPDX-License-Identifier: GPL-3.0-or-later
 * MU1427 diagnostic decoder. Architecture informed by LuKa's cover-art
 * worker (GPL-3.0); stb_image is unmodified and retains its MIT/public-domain
 * notice. All work runs in the supervised child, never the native/HMI thread.
 */
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

#define N3_BUDGET (64u*1024u*1024u)
static size_t n3_used,n3_peak;
/* Eight-byte prefix preserves ARM's eight-byte malloc alignment. */
static void *n3_alloc(size_t n) {
    size_t *p;
    if (!n || n>N3_BUDGET-8 || n3_used>N3_BUDGET-n-8) return NULL;
    p=(size_t *)malloc(n+8);if (!p) return NULL;
    *p=n+8;n3_used+=n+8;if (n3_used>n3_peak)n3_peak=n3_used;
    return (unsigned char *)p+8;
}
static void n3_free(void *p) {
    size_t *q;if (!p)return;q=(size_t *)((unsigned char *)p-8);
    n3_used-=*q;free(q);
}
static void *n3_realloc(void *p,size_t n) {
    size_t old;void *q;
    if (!p)return n3_alloc(n);
    if (!n){n3_free(p);return NULL;}
    old=*(size_t *)((unsigned char *)p-8)-8;
    q=n3_alloc(n);if (!q)return NULL;
    memcpy(q,p,old<n?old:n);n3_free(p);return q;
}
#define STBI_MALLOC(n) n3_alloc(n)
#define STBI_REALLOC(p,n) n3_realloc(p,n)
#define STBI_FREE(p) n3_free(p)
#define STBI_MAX_DIMENSIONS 4096
#define STBI_NO_THREAD_LOCALS
#define STBI_NO_STDIO
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#define STB_IMAGE_IMPLEMENTATION
#include "vendor/stb_image.h"

static unsigned n3_u16(const unsigned char *p,int le) {
    return le?(unsigned)p[0]|(unsigned)p[1]<<8:(unsigned)p[0]<<8|p[1];
}
static uint32_t n3_u32(const unsigned char *p,int le) {
    return le?(uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24:
        (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];
}
/* Parse only a bounded APP1 TIFF IFD0 orientation; never follow thumbnails,
 * arbitrary pointers or strings. Invalid/missing EXIF uses orientation 1.
 */
static unsigned n3_orientation(const unsigned char *b,size_t n) {
    size_t at=2;
    if (n<4 || b[0]!=255 || b[1]!=216)return 1;
    while (at+4<=n) {
        unsigned marker,len;size_t start,end;
        if (b[at++]!=255)return 1;
        while (at<n && b[at]==255)at++;
        if (at>=n)return 1;marker=b[at++];
        if (marker==0xda || marker==0xd9)return 1;
        if (marker==0x01 || (marker>=0xd0 && marker<=0xd7))continue;
        if (at+2>n)return 1;len=n3_u16(b+at,0);
        if (len<2 || len>n-at)return 1;
        start=at+2;end=at+len;
        if (marker==0xe1 && end-start>=14 && !memcmp(b+start,"Exif\0\0",6)) {
            const unsigned char *t=b+start+6;size_t tn=end-start-6,off,i,count;
            int le=t[0]=='I' && t[1]=='I';
            if (!le && !(t[0]=='M' && t[1]=='M'))return 1;
            if (n3_u16(t+2,le)!=42)return 1;
            off=n3_u32(t+4,le);if(off>tn-2)return 1;
            count=n3_u16(t+off,le);off+=2;
            if (count>(tn-off)/12)return 1;
            for(i=0;i<count;i++,off+=12) {
                if(n3_u16(t+off,le)==0x112 && n3_u16(t+off+2,le)==3 && n3_u32(t+off+4,le)==1) {
                    unsigned o=n3_u16(t+off+8,le);return o>=1 && o<=8?o:1;
                }
            }
        }
        at=end;
    }
    return 1;
}
static void n3_be32(unsigned char *p,uint32_t v) {
    p[0]=(unsigned char)(v>>24);p[1]=(unsigned char)(v>>16);
    p[2]=(unsigned char)(v>>8);p[3]=(unsigned char)v;
}
static uint32_t n3_crc(const unsigned char *p,size_t n) {
    uint32_t c=0xffffffffu;size_t i;unsigned k;
    for(i=0;i<n;i++){c^=p[i];for(k=0;k<8;k++)c=(c>>1)^(0xedb88320u & (0u-(c&1)));}
    return ~c;
}
static size_t n3_chunk(unsigned char *p,const char *type,const unsigned char *data,size_t n) {
    n3_be32(p,(uint32_t)n);memcpy(p+4,type,4);
    if(n)memcpy(p+8,data,n);n3_be32(p+8+n,n3_crc(p+4,n+4));return n+12;
}
static int n3_write(const char *path,const unsigned char *data,size_t n) {
    size_t done=0;int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600),ok=1;
    if(fd<0)return 0;
    while(done<n) {
        ssize_t r=write(fd,data+done,n-done);
        if(r<0 && errno==EINTR)continue;
        if(r<=0){ok=0;break;}done+=(size_t)r;
    }
    if(close(fd))ok=0;return ok;
}
/* Exact 256x256 RGB PNG using uncompressed DEFLATE. This bounds output and
 * requires no zlib/libm imports on the factory system. */
static int n3_png(const unsigned char *rgb,const char *path) {
    enum {RAW=256*(256*3+1),ZMAX=RAW+32,PMAX=ZMAX+64};
    unsigned char *raw=n3_alloc(RAW),*z=n3_alloc(ZMAX),*png=n3_alloc(PMAX);
    size_t y,at=2,off=0,pos=8;uint32_t a=1,b=0;int ok=0;
    unsigned char ihdr[13]={0,0,1,0,0,0,1,0,8,2,0,0,0};
    if(!raw || !z || !png)goto done;
    for(y=0;y<256;y++){raw[y*769]=0;memcpy(raw+y*769+1,rgb+y*768,768);}
    z[0]=0x78;z[1]=0x01;
    while(off<RAW) {
        unsigned len=(RAW-off)>65535?65535:(unsigned)(RAW-off);
        z[at++]=(unsigned char)(off+len==RAW);z[at++]=(unsigned char)len;z[at++]=(unsigned char)(len>>8);
        z[at++]=(unsigned char)~len;z[at++]=(unsigned char)(~len>>8);
        memcpy(z+at,raw+off,len);at+=len;off+=len;
    }
    for(y=0;y<RAW;y++){a=(a+raw[y])%65521;b=(b+a)%65521;}
    n3_be32(z+at,(b<<16)|a);at+=4;
    memcpy(png,"\x89PNG\r\n\x1a\n",8);
    pos+=n3_chunk(png+pos,"IHDR",ihdr,13);
    pos+=n3_chunk(png+pos,"IDAT",z,at);
    pos+=n3_chunk(png+pos,"IEND",NULL,0);
    ok=n3_write(path,png,pos);
done:n3_free(raw);n3_free(z);n3_free(png);return ok;
}
struct n3_image_info {unsigned width,height,orientation;size_t peak;};
static int n3_decode(const unsigned char *b,size_t n,const char *path,struct n3_image_info *info) {
    int w=0,h=0,c=0;unsigned o,ow,oh,nw,nh,x,y,x0,y0;unsigned char *rgb=NULL,*canvas=NULL;
    int ok=0,jpeg=n>=3 && b[0]==255 && b[1]==216 && b[2]==255;
    int png=n>=8 && !memcmp(b,"\x89PNG\r\n\x1a\n",8);
    memset(info,0,sizeof(*info));n3_peak=n3_used;
    if(n<8 || n>800000 || (!jpeg && !png))return 0;
    if(!stbi_info_from_memory(b,(int)n,&w,&h,&c) || w<=0 || h<=0 || w>4096 || h>4096 ||
       (uint64_t)(unsigned)w*(unsigned)h>8u*1024u*1024u)return 0;
    rgb=stbi_load_from_memory(b,(int)n,&w,&h,&c,3);if(!rgb)goto done;
    o=n3_orientation(b,n);ow=o>=5?(unsigned)h:(unsigned)w;oh=o>=5?(unsigned)w:(unsigned)h;
    if(ow>=oh){nw=256;nh=(oh*256+ow/2)/ow;}else{nh=256;nw=(ow*256+oh/2)/oh;}
    if(!nw)nw=1;if(!nh)nh=1;
    x0=(256-nw)/2;y0=(256-nh)/2;
    canvas=n3_alloc(256*256*3);if(!canvas)goto done;memset(canvas,0,256*256*3);
    for(y=0;y<nh;y++)for(x=0;x<nw;x++) {
        unsigned tx=x*ow/nw,ty=y*oh/nh,sx=tx,sy=ty;
        switch(o) {
            case 2:sx=(unsigned)w-1-tx;break;
            case 3:sx=(unsigned)w-1-tx;sy=(unsigned)h-1-ty;break;
            case 4:sy=(unsigned)h-1-ty;break;
            case 5:sx=ty;sy=tx;break;
            case 6:sx=ty;sy=(unsigned)h-1-tx;break;
            case 7:sx=(unsigned)w-1-ty;sy=(unsigned)h-1-tx;break;
            case 8:sx=(unsigned)w-1-ty;sy=tx;break;
            default:break;
        }
        memcpy(canvas+((y+y0)*256+x+x0)*3,rgb+((size_t)sy*(unsigned)w+sx)*3,3);
    }
    ok=n3_png(canvas,path);info->width=(unsigned)w;info->height=(unsigned)h;info->orientation=o;
done:info->peak=n3_peak;n3_free(canvas);stbi_image_free(rgb);return ok;
}
