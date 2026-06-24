#!/usr/bin/env bash
set -euo pipefail

echo "Dumping database to docker/initdb/seed.sql.gz ..."
docker compose exec -T postgres pg_dump \
  -U app -d polymarket \
  --no-owner --no-acl \
  | gzip -9 \
  > docker/initdb/seed.sql.gz

SIZE=$(wc -c < docker/initdb/seed.sql.gz | tr -d ' ')
echo "Done.  ${SIZE} bytes written."
echo ""
echo "Next steps:"
echo "  git add docker/initdb/seed.sql.gz"
echo "  git commit -m \"chore: refresh seed dump\""
