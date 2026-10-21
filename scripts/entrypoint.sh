#!/usr/bin/env bash
# Entry point of the backend: everything is configured through environment variables, see
# scripts/run_livestream.sh for the full list and defaults.
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_livestream.sh" "$@"
