#!/bin/bash
set -euo pipefail

# Copy the SQLite database to a timestamped backup file.
SRC="${1:-data/radar.db}"
DEST_DIR="${2:-data}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
cp "$SRC" "$DEST_DIR/radar-$STAMP.db"
echo "backup written to $DEST_DIR/radar-$STAMP.db"
