/* SPDX-License-Identifier: GPL-3.0-or-later
 * Preserve the OEM policy and any higher priority. Only the pinned receiver's
 * alternate sender (port 9997), and the dedicated input adapter, get this floor.
 */
static int (*next_pthread_create)(pthread_t *,const pthread_attr_t *,void *(*)(void *),void *);
struct wcp_thread_start {void *(*entry)(void *);void *arg;};
static void wcp_priority_floor(const char *role) {
    int policy=0,before=-1,after=-1,error;struct sched_param param;char text[160];int n;
    error=pthread_getschedparam(pthread_self(),&policy,&param);
    if(!error) {
        before=param.sched_priority;
        if(before<14) {param.sched_priority=14;error=pthread_setschedparam(pthread_self(),policy,&param);}
        if(!error)error=pthread_getschedparam(pthread_self(),&policy,&param);
        if(!error)after=param.sched_priority;
    }
    n=snprintf(text,sizeof(text),"WCP_PRIORITY role=%s policy=%d before=%d after=%d error=%d\n",role,policy,before,after,error);
    if(n>0 && n<(int)sizeof(text))write(2,text,n);
}
static int wcp_promote_thread(void *(*entry)(void *),void *arg) {
    /* e65ac stores port at parent+200, pthread_create passes parent+136.
     * Audio/main-screen threads and unrecognised receiver builds are excluded. */
    return input_mode || (enabled && (uintptr_t)entry==0xe6fccU && arg && *(const uint32_t *)((const char *)arg+64)==9997);
}
static void *wcp_thread_entry(void *opaque) {
    struct wcp_thread_start start;memcpy(&start,opaque,sizeof(start));free(opaque);
    wcp_priority_floor(input_mode?"input-9997":"receiver-alt");
    return start.entry(start.arg);
}
int pthread_create(pthread_t *thread,const pthread_attr_t *attr,void *(*entry)(void *),void *arg) {
    struct wcp_thread_start *start;int rc;
    if(!next_pthread_create)next_pthread_create=dlsym(RTLD_NEXT,"pthread_create");
    if(!next_pthread_create)return ENOSYS;
    if(!wcp_promote_thread(entry,arg))return next_pthread_create(thread,attr,entry,arg);
    start=malloc(sizeof(*start));
    if(!start)return ENOMEM;
    start->entry=entry;start->arg=arg;
    rc=next_pthread_create(thread,attr,wcp_thread_entry,start);if(rc)free(start);return rc;
}
