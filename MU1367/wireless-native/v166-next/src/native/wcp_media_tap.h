/* SPDX-License-Identifier: GPL-3.0-or-later
 * All state below uses guard. No image decoding or disk I/O on a receiver
 * callback. Complete FT bytes are copied into owned storage, never borrowed.
 */
#include "wcp_media.h"
static struct wcp_media media;
static uint64_t media_received,media_ft_uid;
static unsigned media_ft_generation,media_ft_id,media_ft_art,media_cover_serial;
static int media_ft_declared;
static uint64_t media_ft_started;
struct wcp_cover {unsigned char *data;unsigned size,generation,art,serial;uint64_t uid;};
static struct wcp_cover media_pending_cover;
static unsigned media_published_cover,media_published_size,media_published_generation,media_published_art;
static uint64_t media_published_uid;
static unsigned long media_updates,media_invalid,media_cover_copied,media_cover_dropped;
static void *next_memcpy;
struct media_trace_event {uint64_t time;unsigned kind,generation,md,pb,reason,art,uid_known,uid_nonzero,bytes;};
static struct media_trace_event media_trace_ring[32];static unsigned media_trace_head,media_trace_count;static unsigned long media_trace_lost;
static void media_trace_locked(unsigned kind,unsigned reason,unsigned bytes){
 struct media_trace_event *e;
 if(media_trace_count==32){media_trace_head=(media_trace_head+1)%32;media_trace_count--;media_trace_lost++;}
 e=&media_trace_ring[(media_trace_head+media_trace_count++)%32];e->time=tap_now();e->kind=kind;e->reason=reason;e->bytes=bytes;
 e->generation=media.generation;e->md=media.diag_md;e->pb=media.diag_pb;e->art=media.art;e->uid_known=(media.known&1)!=0;e->uid_nonzero=media.uid!=0;
}
static void media_trace_publish(void){
 struct media_trace_event local[32];unsigned count,i;unsigned long lost;FILE *f;struct stat st;
 const char *path="/ramdisk/cpmap-media-events.log";
 pthread_mutex_lock(&guard);count=media_trace_count;for(i=0;i<count;i++)memcpy(&local[i],&media_trace_ring[(media_trace_head+i)%32],sizeof(local[i]));
 media_trace_head=media_trace_count=0;lost=media_trace_lost;pthread_mutex_unlock(&guard);
 if(!count)return;if(!lstat(path,&st)&&!S_ISREG(st.st_mode))return;
 if(!lstat(path,&st)&&st.st_size>32768){unlink("/ramdisk/cpmap-media-events.log.1");rename(path,"/ramdisk/cpmap-media-events.log.1");}
 f=fopen(path,"a");if(!f)return;
 for(i=0;i<count;i++){struct media_trace_event *e=&local[i];fprintf(f,"WCP_MEDIA_EVENT t_us=%llu kind=%u generation=%u md_mask=%08x pb_mask=%08x reason=%u art=%u uid_known=%u uid_nonzero=%u bytes=%u diag_lost=%lu\n",(unsigned long long)e->time,e->kind,e->generation,e->md,e->pb,e->reason,e->art,e->uid_known,e->uid_nonzero,e->bytes,lost);}
 fclose(f);
}

static void media_clear_locked(void) {
    memset(&media,0,sizeof(media));media_received=media_ft_started=0;
    free(media_pending_cover.data);memset(&media_pending_cover,0,sizeof(media_pending_cover));
    media_ft_generation=0;media_ft_declared=0;
}
static void media_cover_clear(const uintptr_t *r) {
    pthread_mutex_lock(&guard);
    media_trace_locked(5,0,0);media_ft_started=0;media_ft_declared=0;
    if(media.art && r[9]==media.art) {
        /* Empty native FT completion explicitly removes this track's image.
         * A new generation also invalidates any already decoded HMI picture. */
        if(!++media.generation)media.generation=1;if(!++media.revision)media.revision=1;
        media_ft_started=0;free(media_pending_cover.data);memset(&media_pending_cover,0,sizeof(media_pending_cover));
    }
    pthread_mutex_unlock(&guard);
}
void *wcp_tap_memcpy(const uintptr_t *r) {
    if(!next_memcpy)next_memcpy=dlsym(RTLD_NEXT,"memcpy");if(!next_memcpy)_exit(126);
    if(enabled)location_identity_frame((uintptr_t *)r);
    /* Native file-session declaration ACK, after accepted 0x04 length setup.
     * edd00 saves 24 bytes; eddd8 saves 16 + 8 argument bytes. Its caller LR
     * is therefore original-SP+44 (saved-register array index 25). Requiring
     * ecb00 excludes every CSM/transport ACK and all other memcpy callers.
     * Bind at declaration, before another track can arrive ahead of byte 1. */
    if(enabled && r[13]==0xedd9cU && r[2]==2 && r[1] && r[25]==0xecb00U) {
        const unsigned char *ack=(const unsigned char *)r[1];
        if(ack[1]==1 && *(int *)0x110a24==(int)ack[0] && *(uint32_t *)0x135e08==0) {
            pthread_mutex_lock(&guard);
            media_ft_generation=media.generation;media_ft_uid=media.uid;media_ft_art=media.art;
            media_ft_id=ack[0];media_ft_started=tap_now();media_ft_declared=1;media_trace_locked(2,0,0);
            pthread_mutex_unlock(&guard);
        }
    }
    /* Pinned native FT append, before its first chunk. r9 = transfer ID;
     * 135e08 = received length. Bind the transfer to track identity NOW, not
     * at completion, so a late cover cannot attach to a reused ID/new song. */
    if(enabled && r[13]==0xee488U && r[9]<=255 && r[2] && *(uint32_t *)0x135e08==0) {
        pthread_mutex_lock(&guard);
        /* Native also accepts undeclared 0x80/0xc0 transfers. In that case
         * bind at the first chunk; never overwrite an earlier declaration. */
        if(!media_ft_declared || media_ft_id!=r[9]) {
            media_ft_generation=media.generation;media_ft_uid=media.uid;
            media_ft_art=media.art;media_ft_id=r[9];media_ft_started=tap_now();media_ft_declared=0;media_trace_locked(3,0,0);
        }
        pthread_mutex_unlock(&guard);
    }
    return next_memcpy;
}
static void media_cover_completed(const uintptr_t *r) {
    struct wcp_cover event;unsigned char *bytes;int valid;
    memset(&event,0,sizeof(event));
    if(r[3]<8 || r[3]>WCP_COVER_MAX || r[9]>255 || *(uint32_t *)0x135e08!=r[3] ||
       (*(uint32_t *)0x135e0c && *(uint32_t *)0x135e0c!=r[3]))return;
    bytes=*(unsigned char **)0x135e14;if(!bytes)return;
    pthread_mutex_lock(&guard);
    valid=media_ft_started && media_ft_generation==media.generation && media_ft_uid==media.uid && media.uid &&
        media_ft_art==media.art && media.art && media_ft_id==media.art && r[9]==media.art;
    if(valid){event.size=r[3];event.generation=media.generation;event.uid=media.uid;event.art=media.art;}
    media_trace_locked(valid?4:6,valid?0:1,(unsigned)r[3]);media_ft_started=0;media_ft_declared=0;
    pthread_mutex_unlock(&guard);
    if(!valid)return;
    event.data=malloc(event.size);if(!event.data)return;
    memcpy(event.data,bytes,event.size);
    pthread_mutex_lock(&guard);
    if(event.generation==media.generation && event.uid==media.uid && event.art==media.art) {
        free(media_pending_cover.data);event.serial=++media_cover_serial;
        if(!event.serial)event.serial=++media_cover_serial;
        memcpy(&media_pending_cover,&event,sizeof(event));media_cover_copied++;
    }else{free(event.data);media_cover_dropped++;media_trace_locked(6,2,event.size);}
    pthread_mutex_unlock(&guard);
}
static void media_publish(int accepted,uint64_t nonce,unsigned session,int was_accepted) {
    static unsigned counter;
    struct wcp_media state;struct wcp_cover cover;unsigned char snapshot[WCP_MEDIA_MAX];
    unsigned published=0,size=0;size_t n;uint64_t now=tap_now();
    pthread_mutex_lock(&guard);
    if((was_accepted && !accepted) || (!was_accepted && accepted && (!media_received || now<media_received || now-media_received>2000000)))media_clear_locked();
    memcpy(&state,&media,sizeof(state));memcpy(&cover,&media_pending_cover,sizeof(cover));memset(&media_pending_cover,0,sizeof(media_pending_cover));
    if(!accepted || media_published_generation!=state.generation || media_published_uid!=state.uid || media_published_art!=state.art)
        media_published_cover=media_published_size=0;
    pthread_mutex_unlock(&guard);
    if(accepted && cover.data && cover.generation==state.generation && cover.uid==state.uid && cover.art==state.art) {
        /* Immutable atomic snapshot: header and bytes share one file inode. */
        unsigned char *out=malloc(64+cover.size);
        if(out) {
            memset(out,0,64);memcpy(out,"WCA1",4);media_le32(out+4,1);media_le32(out+8,64+cover.size);
            media_le32(out+12,getpid());media_le32(out+16,nonce);media_le32(out+20,nonce>>32);media_le32(out+24,session);
            media_le32(out+28,cover.generation);media_le32(out+32,cover.uid);media_le32(out+36,cover.uid>>32);
            media_le32(out+40,cover.art);media_le32(out+44,cover.serial);media_le32(out+48,cover.size);memcpy(out+64,cover.data,cover.size);
            if(atomic_file("cover.bin",out,64+cover.size)) {
                media_published_generation=cover.generation;media_published_uid=cover.uid;media_published_art=cover.art;
                media_published_cover=cover.serial;media_published_size=cover.size;
            }
            free(out);
        }
    }
    free(cover.data);
    if(!accepted)unlink("/ramdisk/wcp-rg/cover.bin");
    published=media_published_cover;size=media_published_size;
    if(!++counter)counter=1;
    n=wcp_media_mailbox(&state,snapshot,sizeof(snapshot),getpid(),nonce,session,counter,accepted,published,size);
    if(n)atomic_file("nowplaying.bin",snapshot,n);
}
