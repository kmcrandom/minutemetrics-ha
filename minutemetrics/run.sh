#!/usr/bin/env sh
set -eu

export PYTHONPATH="/app/src"
exec /opt/minutemetrics/bin/python3 -m minutemetrics

