# Source and attribution

Project changes are GPL-3.0-or-later. The integrated VC core/menu/runtime sources
retain the upstream omonob license and notices in `src/runtime/LICENSE`.
Source: https://github.com/omonob/MHI2-Carplay-Maps (reviewed runtime revision
2f5fd58b63b48b807d59c5f79795847fc8c50d05).

Android Auto (v1.5.0-e) uses, under GPL-3.0-or-later: the `gal` cluster-map hook of
https://github.com/MacsInSpace/mib-cluster-map (commit
07361db860b1d09e3901e9002b4222889a8a8c18), built with the pmcp patches, the AA route
translation (`pmcp_rg.c`) and the `aa-most-feeder` of
https://github.com/chrzanowy/mhi2-aid-carplay (commit
af98480112937b908b7604379fa35e0ddd64fcb4). The hook and `libdmdt_flush.so` binaries are
those pinned there; sources, recipe and provenance are in `src/android-auto`. The
feeder is rebuilt here with MU1367 changes.

The Toolbox distribution retains its own authorship/license files. The artwork
decoder retains the stb_image license in its header. Native guidance research
also benefited from perkthefox/mst2-cluster-nav, MacsinSpace's MIB projects,
luka-dev/mib2q-carplay-rgi, fifthBro/mh2p-cluster and brisoleg/e-golf-mib2.
The OMKE and Ottocast analyses are references; their binaries are not executed
or flashed by this release.

Maintained source and build/recovery tooling:
https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/MU1367-v1.4.3/MU1367/integration

Factory classes/binaries are specific to the matching firmware. Build tools
require the owner's exact factory inputs and refuse mismatched fingerprints.
