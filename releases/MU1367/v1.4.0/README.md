# MU1367 v1.4.0 — native lane guidance

Ready-to-extract full SD toolbox for exact K4525 MU1367 + AID 791.
[Download ZIP](CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip?raw=true) ·
[SHA256SUMS.txt](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

Existing v1.3.0 installations use **step 4 only**. Refresh Toolbox menus and
scripts, disconnect CarPlay and reboot first. See the
[installation, acceptance and full rollback guide](../../../MU1367/lanes/INSTALL.md).
Fresh installs complete the original three stages before adding lanes.

The lane layer supplies phone lane geometry/recommendations to the factory
renderer and defaults turn cards OFF. The existing App-Connect ON/OFF control
remains available. Saved preferences are retained; select OFF once if Card ON
was previously saved. The original v1.3.0 release is unchanged.

Offline protocol/factory-runtime, transaction recovery and complete no-SD
OEM restoration checks pass. The user subsequently
[reported successful vehicle operation](../../../MU1367/lanes/UNIT-RESULTS.md),
and this is now a regular release. Individual app/route results and endurance
duration were not supplied. The ZIP and build-time records are unchanged;
bundled documents retain their original pre-test wording.

ZIP SHA256: `942c9d2a1b38e7f417f97e1a8806e42559b29565f3605215c92b932d58c1259f`.
