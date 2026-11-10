#!/bin/sh
exec /usr/bin/python3 -I "$(dirname "$0")/fake_bridge.py"
