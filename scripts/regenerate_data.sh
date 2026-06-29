#!/usr/bin/env bash
# OPTIONAL — rebuild ALL rustdoc JSON from qdrant source, including the 18M `segment` crate the
# committed seed omits. You only need this to re-run the eval against the full 5-crate graph, or to
# refresh from a newer qdrant. notebooks 01/02 work without it (committed assets + setup_data.sh).
#
# Requires a Rust NIGHTLY toolchain (rustdoc JSON is nightly-only) and is slow (several minutes; it
# compiles each crate's dependency tree). It is documented but NOT part of the attendee critical path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QDRANT_COMMIT="44ad62f8cd69642be5afa6441612525e24a0d063"   # pinned: the corpus the committed cache was built from
QDRANT_DIR="$ROOT/data/raw_repos/qdrant"

if [ ! -d "$QDRANT_DIR/.git" ]; then
  echo "cloning qdrant @ $QDRANT_COMMIT …"
  git clone --filter=blob:none https://github.com/qdrant/qdrant.git "$QDRANT_DIR"
fi
git -C "$QDRANT_DIR" fetch origin "$QDRANT_COMMIT" 2>/dev/null || git -C "$QDRANT_DIR" fetch origin
git -C "$QDRANT_DIR" checkout -q "$QDRANT_COMMIT"

NIGHTLY=$(echo "$HOME"/.rustup/toolchains/nightly-*/bin)
export PATH="$NIGHTLY:$PATH"
export CARGO_TARGET_DIR="$ROOT/data/cache/cargo-target"
command -v rustc >/dev/null || { echo "no rust toolchain on PATH — install rustup + a nightly"; exit 1; }
echo "toolchain: $(rustc --version)"

for crate in posting_list sparse gridstore quantization segment; do
  man="$QDRANT_DIR/lib/$crate/Cargo.toml"
  [ -f "$man" ] || { echo "skip $crate (no Cargo.toml)"; continue; }
  echo "rustdoc → $crate …"
  cargo rustdoc --manifest-path "$man" -- -Z unstable-options --output-format json
done
echo "✓ regenerated rustdoc JSON for 5 crates under data/cache/cargo-target/doc/"
