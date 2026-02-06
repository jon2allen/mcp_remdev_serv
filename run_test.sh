#!/bin/bash

# Configuration for the FreeBSD remote server
export REMOTE_HOST="192.168.200.129"
export REMOTE_PORT="4022"
export REMOTE_OS_TYPE="freebsd"
export REMOTE_DIR="/home/jon2allen/vibe_test"

# Optional: Set this to false if you want to test security blocking
export REMOTE_OVERRIDE_SECURITY="true"

echo "Environment Variables Set:"
echo "REMOTE_HOST: $REMOTE_HOST"
echo "REMOTE_PORT: $REMOTE_PORT"
echo "REMOTE_OS_TYPE: $REMOTE_OS_TYPE"
echo "REMOTE_DIR: $REMOTE_DIR"
echo "--------------------------------"

# Run the test script
python3 test_tools.py
