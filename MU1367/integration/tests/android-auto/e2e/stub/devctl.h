/* Host-test stub: the bridge's ALTSCREEN_BRIDGE_FILE_OUTPUT build writes MPEG-TS to a file
 * and never issues a QNX devctl; any remaining call fails like an unsupported device. */
#ifndef CPMAP_HOST_DEVCTL_H
#define CPMAP_HOST_DEVCTL_H
#include <errno.h>
#include <stddef.h>
static inline int devctl(int fd, int cmd, void *data, size_t size, int *info)
{ (void)fd; (void)cmd; (void)data; (void)size; if (info) *info = 0; return ENOTTY; }
#endif
