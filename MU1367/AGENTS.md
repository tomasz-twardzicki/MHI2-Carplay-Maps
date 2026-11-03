# MU1367 target command compatibility

Current development is based on the published v1.4.3 integration, including
P4521 recognition and the v1.4.2 U-turn fix. v1.4.3-e adds experimental reader
recovery to that baseline. Use the current integration sources and release
manifests for further changes; the v1.4.1-only reader add-on is historical.
Keep both K4525 and P4521 support, exact firmware gates and snapshot recovery.

Before introducing a shell command or a new command option for the unit, verify
it against the actual matching firmware or a captured live-unit availability
check. An SDK installation or an emulator augmented with SDK-only utilities is
not evidence that the unit provides it.

Check required commands before persistent writes. Treat optional diagnostic
commands as optional. Run QNX compatibility tests with firmware-extracted
utilities; do not add unavailable commands to make a test pass. The OEM reset's
`COMMANDS.json`, `audit_commands.py` and read-only `check-tools` action provide
the current command inventory and live check.
