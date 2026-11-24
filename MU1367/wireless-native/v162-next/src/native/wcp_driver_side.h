/* SPDX-License-Identifier: GPL-3.0-or-later
 * Merge OEM driver coding into a RAM-only copy of this unit's receiver config.
 * The original config and WCP_DATA (pairing store) never change.
 */
static FILE *(*next_fopen)(const char *,const char *);
static volatile int config_merging;
typedef void *WcpObject;
static int wcp_driver_side(void) {
    static const char *paths[]={"/ramdisk/cpmap-driver-side.state","/mnt/persist/cpmap-driver-side.state"};
    unsigned i;
    for(i=0;i<2;i++) {
        char text[16];struct stat st;FILE *f;size_t n;
        if(lstat(paths[i],&st) || !S_ISREG(st.st_mode) || st.st_size!=8)continue;
        f=next_fopen(paths[i],"r");if(!f)continue;
        n=fread(text,1,sizeof(text),f);fclose(f);
        if(n==8 && !memcmp(text,"CPDS1\n",6) && text[7]=='\n' && (text[6]=='1' || text[6]=='2'))return text[6]-'0';
    }
    return 0;
}
static void wcp_cf_release(WcpObject p) {if(p)((void (*)(WcpObject))0x51ce8)(p);}
static WcpObject wcp_cf_empty_dict(void) {
    return ((WcpObject (*)(WcpObject,int,void *,void *))0x52060)(0,0,(void *)0x20104,(void *)0x2011c);
}
static void wcp_oem_label(WcpObject dict) {
    WcpObject key=((WcpObject (*)(WcpObject,const char *,unsigned))0x52220)(0,"oemIconLabel",0x80000100);
    WcpObject value=((WcpObject (*)(WcpObject,const char *,unsigned))0x52220)(0,"Volkswagen",0x80000100);
    if(dict && key && value)((void (*)(WcpObject,WcpObject,WcpObject))0x520d0)(dict,key,value);
    wcp_cf_release(value);wcp_cf_release(key);
}
static FILE *wcp_driver_config(const char *path) {
    struct stat st;char output[160];FILE *f=0,*merged=0;
    WcpObject original=0,dict=0,data=0,empty=0;int side=0,missing;const void *bytes;int length;
    side=wcp_driver_side();
    missing=lstat(path,&st)!=0;
    if(missing && errno!=ENOENT)return 0;
    if(!missing && (!S_ISREG(st.st_mode) || st.st_size<1 || st.st_size>65536))return 0;
    empty=wcp_cf_empty_dict();if(!empty)goto done;
    if(missing) {dict=empty;empty=0;}
    else {
        original=((WcpObject (*)(const char *,void *))0x595e4)(path,0);if(!original)goto done;
        dict=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,original,1,0,0);
        /* Match the receiver's existing binary-plist / INI support. */
        if(!dict) {
            bytes=((void *(*)(WcpObject))0x51e18)(original);length=((int (*)(WcpObject))0x51e40)(original);
            if(bytes && length>0 && length<=65536)dict=((WcpObject (*)(const void *,int,int,WcpObject,void *))0x5905c)(bytes,length,1,(WcpObject)0x3ea50,0);
        }
        if(!dict || ((unsigned (*)(WcpObject))0x51cc0)(dict)!=((unsigned (*)(WcpObject))0x51cc0)(empty))goto done;
    }
    if(side==1 || side==2)((void (*)(WcpObject,WcpObject,WcpObject))0x520d0)(dict,(WcpObject)0x3eaf2,*(WcpObject *)(side==2?0x110418:0x110424));
    wcp_oem_label(dict);
    data=((WcpObject (*)(WcpObject,WcpObject,int,int,void *))0x52470)(0,dict,200,0,0);
    if(!data)goto done;
    bytes=((void *(*)(WcpObject))0x51e18)(data);length=((int (*)(WcpObject))0x51e40)(data);
    if(!bytes || length<=0 || length>65536)goto done;
    snprintf(output,sizeof(output),"/ramdisk/wcp-rg/airplay.merged-%ld",(long)getpid());
    f=next_fopen(output,"w+");if(!f)goto done;
    if(fwrite(bytes,1,length,f)!=(size_t)length || fflush(f) || fseek(f,0,SEEK_SET)) {fclose(f);unlink(output);goto done;}
    merged=f;
done:
    wcp_cf_release(empty);wcp_cf_release(data);wcp_cf_release(dict);wcp_cf_release(original);return merged;
}
/* Always-executed strlcpy in the pinned /info builder. r5 is the owned
 * response dictionary, r6 the server, +124 its mutable in-memory config.
 * Refresh on the request thread so late coding replaces the startup value.
 * No pairing/config file is changed. The call-site guard excludes all other
 * strlcpy users (including those in the preloaded dependencies). */
static void *next_strlcpy;
void *wcp_tap_strlcpy(const uintptr_t *r) {
    if(!next_strlcpy)next_strlcpy=dlsym(RTLD_NEXT,"strlcpy");
    if(!next_strlcpy)_exit(126);
    if(enabled && r[13]==0xce990U && r[1]==0x1bef2U && r[2]==1025 && r[5] && r[6]) {
        int side=wcp_driver_side();
        WcpObject config=*(WcpObject *)(r[6]+124);
        wcp_oem_label((WcpObject)r[5]);if(config)wcp_oem_label(config);
        if(side) {
            WcpObject value=*(WcpObject *)(side==2?0x110418:0x110424);
            ((void (*)(WcpObject,WcpObject,WcpObject))0x520d0)((WcpObject)r[5],(WcpObject)0x3eaf2,value);
            if(config)((void (*)(WcpObject,WcpObject,WcpObject))0x520d0)(config,(WcpObject)0x3eaf2,value);
        }
    }
    return next_strlcpy;
}
FILE *fopen(const char *path,const char *mode) {
    char expected[512];const char *directory;
    if(!next_fopen)next_fopen=dlsym(RTLD_NEXT,"fopen");
    if(!next_fopen){errno=ENOSYS;return 0;}
    if(enabled && path && mode && (!strcmp(mode,"r") || !strcmp(mode,"rb"))) {
        directory=getenv("WCP_DATA");if(!directory || !*directory)directory="/mnt/persist/wcp";
        if(snprintf(expected,sizeof(expected),"%s/airplay.conf",directory)<(int)sizeof(expected) && !strcmp(path,expected) &&
           __sync_bool_compare_and_swap(&config_merging,0,1)) {
            FILE *f=wcp_driver_config(path);__sync_synchronize();config_merging=0;
            if(f)return f;
        }
    }
    return next_fopen(path,mode);
}
