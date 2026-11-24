/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef WCP_MEDIA_H
#define WCP_MEDIA_H
#include <stdint.h>
#include <stddef.h>
#define WCP_MEDIA_TEXT 1024
#define WCP_MEDIA_MAX 8192
#define WCP_COVER_MAX 800000
struct wcp_media {
    uint64_t uid;
    uint32_t generation,revision,known,duration,position,status,shuffle,repeat,art;
    char text[6][WCP_MEDIA_TEXT+1]; /* title, artist, album, genre, composer, app */
};
/* Atomic delta merge: malformed or duplicate parameters never partly commit. */
int wcp_media_message(struct wcp_media *,const unsigned char *,size_t);
size_t wcp_media_mailbox(const struct wcp_media *,unsigned char *,size_t,uint32_t,uint64_t,uint32_t,uint32_t,int,uint32_t,uint32_t);
#endif
