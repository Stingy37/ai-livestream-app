#!/usr/bin/env bash
# Thin wrapper: deploy the EC2 broadcast server + website (see ec2/deploy.sh for the settings).
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/ec2/deploy.sh" "$@"
