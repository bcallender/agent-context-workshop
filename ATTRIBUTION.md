# Attribution

## Corpus: qdrant

This workshop's example codebase is [**qdrant**](https://github.com/qdrant/qdrant), the
open-source vector database, licensed under the **Apache License 2.0**.

- Source: <https://github.com/qdrant/qdrant>
- Pinned commit: `44ad62f8cd69642be5afa6441612525e24a0d063`

Under `assets/source/qdrant/lib/` we redistribute the source of four crates
(`posting_list`, `sparse`, `gridstore`, `quantization`) so the notebooks can parse real code
offline, plus rustdoc JSON **derived** from that source under `assets/rustdoc/`. A copy of
qdrant's license travels with the source at `assets/source/qdrant/LICENSE`. qdrant ships no
`NOTICE` file, so there is none to reproduce, and its source carries no per-file copyright
headers.

The committed eval cache (`data/eval/`) contains only numeric aggregates (hit rates, token
counts) — no model output text.

## This workshop

All original workshop code — everything outside `assets/source/qdrant/` — is licensed under the
Apache License 2.0; see [`LICENSE`](LICENSE).
