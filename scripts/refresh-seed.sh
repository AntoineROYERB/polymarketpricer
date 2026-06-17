#!/usr/bin/env bash
set -euo pipefail

echo "Dumping database to docker/initdb/seed.sql ..."
docker compose exec -T postgres pg_dump \
  -U app -d polymarket \
  --no-owner --no-acl \
  --exclude-table-data='alembic_version' \
  > docker/initdb/seed.sql

SIZE=$(wc -c < docker/initdb/seed.sql | tr -d ' ')
echo "Done.  ${SIZE} bytes written."
echo ""
echo "Next steps:"
echo "  git add docker/initdb/seed.sql"
echo "  git commit -m \"chore: refresh seed dump\""
