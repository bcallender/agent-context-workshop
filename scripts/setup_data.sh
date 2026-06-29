#!/usr/bin/env bash
# Hydrate the committed seed (assets/) into the data/ paths the notebooks expect. Idempotent.
#   - notebook 02 (the eval) needs NOTHING from this — it reads the committed cache in data/eval/.
#   - notebook 01 needs the 4 crates' rustdoc JSON (Rung 1) + raw source (Rung 0, tree-sitter).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOC="$ROOT/data/cache/cargo-target/doc"
LIB="$ROOT/data/raw_repos/qdrant/lib"
mkdir -p "$DOC" "$LIB"

for c in posting_list sparse gridstore quantization; do
  [ -f "$DOC/$c.json" ] || gunzip -c "$ROOT/assets/rustdoc/$c.json.gz" > "$DOC/$c.json"
  [ -d "$LIB/$c" ]      || cp -R "$ROOT/assets/source/qdrant/lib/$c" "$LIB/$c"
done

echo "✓ data hydrated: 4 crates (rustdoc JSON + source) for notebook 01."
echo "  notebook 02 (the eval) needs nothing further."
echo "  notebook 01 Level 3 needs Neo4j running:  docker compose up -d"
echo "  full 5-crate set (incl. segment) for re-running the eval:  scripts/regenerate_data.sh"
