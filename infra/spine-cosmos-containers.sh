#!/usr/bin/env bash
#
# Provision the 4 Cosmos SQL containers backing the spine observability layer.
#
# This project does not have a checked-in Bicep/IaC pipeline for Cosmos;
# container lifecycle is managed with az CLI. This script is the source of
# truth for the spine containers' partition keys and TTLs.
#
# Idempotent: re-running against an already-provisioned account will report
# a 409 Conflict for each existing container. Safe.
#
# First provisioned: 2026-04-15 (Phase 1 / spine foundation).

set -euo pipefail

RG="${RG:-shared-services-rg}"
ACCOUNT="${ACCOUNT:-shared-services-cosmosdb}"
DB="${DB:-second-brain}"

echo "Provisioning spine containers in ${ACCOUNT}/${DB} (${RG})..."

# 1. Segment state — one doc per segment, never expires (always upserted).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_segment_state \
  --partition-key-path /segment_id \
  --ttl=-1

# 2. Ingest events — append-only, 14-day retention (1209600 seconds).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_events \
  --partition-key-path /segment_id \
  --ttl=1209600

# 3. Status transition history — append-only, 30-day retention (2592000 seconds).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_status_history \
  --partition-key-path /segment_id \
  --ttl=2592000

# 4. Correlation records — append-only, 30-day retention, keyed on correlation_kind.
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_correlation \
  --partition-key-path /correlation_kind \
  --ttl=2592000

echo "Done. Verifying..."
az cosmosdb sql container list -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --query "[?starts_with(name, 'spine_')].{name:name, partitionKey:resource.partitionKey.paths[0], ttl:resource.defaultTtl}" \
  -o table
