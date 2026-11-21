# v1.6.3-e — experimental pre-release

- Retains the exact sealed v1.6.3-e-test2 wireless runtime and recovery identity.
- Complete OEM restore covers omonob's public plaintext wired releases and
  wireless v3.0/v3.1/v3.2: factory BT/connection manager, HMI bundles, production
  configs, mm-ipod and Android Auto host are restored; addon JARs, startup hooks
  and flags are removed. Old management/recovery material is preserved.
- The complete SD provides the fresh base and wireless installation, separated
  by full reboots. No separate v1.5.4 installation is required.
- Confirms the packaged navigation-card preference defaults to Off; saved
  choices remain intact.
- Retains completed OEM snapshots before a new installation.

K4525/P4521 MU1367 + AID 791 only. Experimental: bench results are not vehicle
acceptance. See START_HERE.md for installation, recovery and validation limits.

Thanks to [omonob](https://github.com/omonob) for the original receiver/maps
implementation and the contributors and drivers credited in test2.
