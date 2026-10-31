# MU1367 target command compatibility

Before introducing a shell command or a new command option for the unit, verify
it against the actual matching firmware or a captured live-unit availability
check. An SDK installation or an emulator augmented with SDK-only utilities is
not evidence that the unit provides it.

Check required commands before persistent writes. Treat optional diagnostic
commands as optional. Run QNX compatibility tests with firmware-extracted
utilities; do not add unavailable commands to make a test pass. The OEM reset's
`COMMANDS.json`, `audit_commands.py` and read-only `check-tools` action provide
the current command inventory and live check.
