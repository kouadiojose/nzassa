#!/usr/bin/env bash
# Sauvegarde PostgreSQL avec rétention (7 quotidiennes / 4 hebdomadaires).
# Usage : ./backup_postgres.sh [répertoire_sortie]
set -euo pipefail

BACKUP_DIR="${1:-/var/backups/nzassa}"
DB_NAME="${POSTGRES_DB:-nzassa}"
DB_USER="${POSTGRES_USER:-nzassa}"
DB_HOST="${POSTGRES_HOST:-localhost}"

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

STAMP="$(date +%F)"
TARGET="$BACKUP_DIR/daily/nzassa_${STAMP}.dump"

pg_dump -Fc -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" > "$TARGET"
echo "Sauvegarde créée : $TARGET"

# Copie hebdomadaire le dimanche
if [ "$(date +%u)" = "7" ]; then
  cp "$TARGET" "$BACKUP_DIR/weekly/"
fi

# Rétention
find "$BACKUP_DIR/daily" -name '*.dump' -mtime +7 -delete
find "$BACKUP_DIR/weekly" -name '*.dump' -mtime +28 -delete
