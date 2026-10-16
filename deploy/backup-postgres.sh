#!/usr/bin/env sh
set -eu

# Run from the deployment directory after exporting BACKUP_DIR. Keep BACKUP_DIR outside the repository.
: "${BACKUP_DIR:?Set BACKUP_DIR to an encrypted/controlled backup directory}"
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/steam-codes-$stamp.sql.gz"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip -9 > "$target"
sha256sum "$target" > "$target.sha256"
find "$BACKUP_DIR" -type f -name 'steam-codes-*.sql.gz' -mtime +14 -delete
find "$BACKUP_DIR" -type f -name 'steam-codes-*.sql.gz.sha256' -mtime +14 -delete
echo "Backup created: $target"
