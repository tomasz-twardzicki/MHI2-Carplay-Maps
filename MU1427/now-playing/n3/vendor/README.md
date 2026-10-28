# Image decoder provenance

`stb_image.h` is the unmodified stb_image v2.30 header from LuKa's
[`mib2q-carplay-rgi`](https://github.com/luka-dev/mib2q-carplay-rgi/blob/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7/hook/coverart/stb_image.h),
pinned at commit `71b4ab1c9461d5383a7aa6d56d4dda34f567ade7`.
SHA-256: `594c2fe35d49488b4382dbfaec8f98366defca819d916ac95becf3e75f4200b3`.
It retains the authors' MIT/public-domain license at the end of the header.

The separate MU1427 worker is GPL-3.0-or-later. Its bounded off-thread decode
architecture follows LuKa's cover-art work, with a native completed-buffer
input, a diagnostic-only output, all eight EXIF orientations and a fixed-size
PNG writer. It does not include LuKa's raw transport reassembler or Audi Java
picture provider. Keep this attribution and the repository LICENSE in source
packages.
