"""The 30-question eval corpus (graph vs grep), gold verified against source.

Classes: typedep (refactoring impact) · collision (cross-crate name clashes) · private
(grep's boundary — v2) · control (parity). Each question carries `advantage` = the graph's
HONEST edge (efficiency / completeness / boundary / parity) — never a single-shot accuracy
claim. `expect` is kept for back-compat but advantage is the truthful label.

For typedep, `anchors` are name-mode (the answer must NAME these key dependents)
and `dependents` is the fuller verified set scored by set-recall. For collision/
private/control, `anchors` are located (basename + line + symbol, crate-guarded).
All file:lines resolved from the graph (public) or tree-sitter (private) and
checked against source by .context/verify_gold.py.
"""


def _named(sym, crate=None):
    a = {"symbol": sym, "mode": "named"}
    if crate:
        a["crate"] = crate
    return a


GOLD = [
    # ===================== A. TYPE-DEPENDENCY / IMPLEMENTORS (15, graph wins) =====================
    dict(
        name="td-postinglist",
        klass="typedep",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="I'm about to change the public `PostingList` in the `posting_list` crate. Which other public "
        "types in the crate directly depend on it (build it, return it, or borrow it) so I know what to check?",
        anchors=[_named("PostingBuilder"), _named("PostingListView")],
        dependents=["posting_list::builder::PostingBuilder", "posting_list::view::PostingListView"],
    ),
    dict(
        name="td-postingvisitor",
        klass="typedep",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="Which public methods or types directly return or take `posting_list::PostingVisitor`?",
        anchors=[_named("PostingIterator")],
        dependents=[
            "posting_list::iterator::PostingIterator",
            "posting_list::posting_list::PostingList",
            "posting_list::view::PostingListView",
        ],
    ),
    dict(
        name="td-valuehandler",
        klass="typedep",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="I want to modify the `ValueHandler` trait in `posting_list`. What types implement it?",
        anchors=[_named("SizedHandler"), _named("UnsizedHandler")],
        dependents=[
            "posting_list::value_handler::SizedHandler",
            "posting_list::value_handler::UnsizedHandler",
        ],
    ),
    dict(
        name="td-encodedvectors",
        klass="typedep",
        crate="quantization",
        expect="graph",
        confidence="high",
        q="I'm changing the `EncodedVectors` trait in `quantization`. What implements it (including anything "
        "outside the quantization crate)?",
        anchors=[_named("EncodedVectorsU8"), _named("QuantizedMultivectorStorage", "segment")],
        dependents=[
            "quantization::encoded_vectors_u8::EncodedVectorsU8",
            "quantization::encoded_vectors_binary::EncodedVectorsBin",
            "quantization::encoded_vectors_pq::EncodedVectorsPQ",
            "quantization::encoded_vectors_tq::EncodedVectorsTQ",
            "segment::vector_storage::quantized::quantized_multivector_storage::QuantizedMultivectorStorage",
        ],
    ),
    dict(
        name="td-vectorparameters",
        klass="typedep",
        crate="quantization",
        expect="graph",
        confidence="high",
        q="If I change `quantization::VectorParameters`, what depends on it (across crates)?",
        anchors=[_named("QuantizedVectorsConfig", "segment")],
        dependents=[
            "quantization::encoded_vectors_pq::Metadata",
            "quantization::encoded_vectors_tq::Metadata",
            "segment::vector_storage::quantized::quantized_vectors::QuantizedVectorsConfig",
        ],
    ),
    dict(
        name="td-encodingerror",
        klass="typedep",
        crate="quantization",
        expect="graph",
        confidence="high",
        q="Which encoder types in `quantization` have an `encode` path that returns `EncodingError`?",
        anchors=[_named("EncodedVectorsU8"), _named("kmeans")],
        dependents=[
            "quantization::encoded_vectors_u8::EncodedVectorsU8",
            "quantization::encoded_vectors_binary::EncodedVectorsBin",
            "quantization::encoded_vectors_pq::EncodedVectorsPQ",
            "quantization::encoded_vectors_tq::EncodedVectorsTQ",
            "quantization::kmeans::kmeans",
        ],
    ),
    dict(
        name="td-tqmode",
        klass="typedep",
        crate="quantization",
        expect="graph",
        confidence="high",
        q="What depends on `quantization::turboquant::TQMode` — i.e. what would I touch if I changed it?",
        anchors=[_named("EncodedVectorsTQ"), _named("TurboQuantizer")],
        dependents=[
            "quantization::encoded_vectors_tq::EncodedVectorsTQ",
            "quantization::encoded_vectors_tq::Metadata",
            "quantization::turboquant::quantization::TurboQuantizer",
        ],
    ),
    dict(
        name="td-storageoptions",
        klass="typedep",
        crate="gridstore",
        expect="graph",
        confidence="high",
        q="Which public `Gridstore` constructors take `gridstore::config::StorageOptions`?",
        anchors=[_named("Gridstore")],
        dependents=[
            "gridstore::gridstore::Gridstore::new",
            "gridstore::gridstore::Gridstore::open_or_create",
        ],
    ),
    dict(
        name="td-compression",
        klass="typedep",
        crate="gridstore",
        expect="graph",
        confidence="high",
        q="If I change `gridstore::config::Compression`, what config type holds it?",
        anchors=[_named("StorageOptions")],
        dependents=["gridstore::config::StorageOptions"],
    ),
    dict(
        name="td-idtracker",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="I'm changing the `IdTracker` trait in `segment`. What implements it?",
        anchors=[_named("MutableIdTracker"), _named("ImmutableIdTracker")],
        dependents=[
            "segment::id_tracker::id_tracker_base::tracker_enum::IdTrackerEnum",
            "segment::id_tracker::immutable_id_tracker::ImmutableIdTracker",
            "segment::id_tracker::in_memory_id_tracker::InMemoryIdTracker",
            "segment::id_tracker::mutable_id_tracker::MutableIdTracker",
        ],
    ),
    dict(
        name="td-vectorindex",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="What implements the `VectorIndex` trait in `segment`?",
        anchors=[_named("HNSWIndex"), _named("SparseVectorIndex")],
        dependents=[
            "segment::index::hnsw_index::hnsw::HNSWIndex",
            "segment::index::plain_vector_index::PlainVectorIndex",
            "segment::index::sparse_index::sparse_vector_index::SparseVectorIndex",
            "segment::index::vector_index_base::VectorIndexEnum",
        ],
    ),
    dict(
        name="td-queryscorer",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="I'm changing the `QueryScorer` trait in `segment`. What implements it that I'd need to update?",
        anchors=[_named("MetricQueryScorer"), _named("QuantizedQueryScorer")],
        dependents=[
            "segment::vector_storage::quantized::quantized_query_scorer::QuantizedQueryScorer",
            "segment::vector_storage::query_scorer::custom_query_scorer::CustomQueryScorer",
            "segment::vector_storage::query_scorer::metric_query_scorer::MetricQueryScorer",
            "segment::vector_storage::query_scorer::multi_custom_query_scorer::MultiCustomQueryScorer",
            "segment::vector_storage::query_scorer::multi_metric_query_scorer::MultiMetricQueryScorer",
            "segment::vector_storage::query_scorer::sparse_custom_query_scorer::SparseCustomQueryScorer",
            "segment::vector_storage::query_scorer::sparse_metric_query_scorer::SparseMetricQueryScorer",
        ],
    ),
    dict(
        name="td-vectorstorage",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="What implements the `VectorStorage` trait in `segment`? Name all of them.",
        anchors=[_named("DenseVectorStorageImpl"), _named("VectorStorageEnum")],
        dependents=[
            "segment::vector_storage::dense::dense_vector_storage::DenseVectorStorageImpl",
            "segment::vector_storage::dense::appendable_dense_vector_storage::AppendableMmapDenseVectorStorage",
            "segment::vector_storage::dense::empty_dense_vector_storage::EmptyDenseVectorStorage",
            "segment::vector_storage::dense::volatile_dense_vector_storage::VolatileDenseVectorStorage",
            "segment::vector_storage::multi_dense::appendable_mmap_multi_dense_vector_storage::AppendableMmapMultiDenseVectorStorage",
            "segment::vector_storage::multi_dense::volatile_multi_dense_vector_storage::VolatileMultiDenseVectorStorage",
            "segment::vector_storage::sparse::empty_sparse_vector_storage::EmptySparseVectorStorage",
            "segment::vector_storage::sparse::mmap_sparse_vector_storage::MmapSparseVectorStorage",
            "segment::vector_storage::sparse::volatile_sparse_vector_storage::VolatileSparseVectorStorage",
            "segment::vector_storage::vector_storage_base::VectorStorageEnum",
        ],
    ),
    dict(
        name="td-distance",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="`segment::types::Distance` drives metric selection. Name the distance-metric implementations that "
        "depend on it.",
        anchors=[_named("CosineMetric"), _named("EuclidMetric")],
        dependents=[
            "segment::spaces::simple::CosineMetric",
            "segment::spaces::simple::DotProductMetric",
            "segment::spaces::simple::EuclidMetric",
            "segment::spaces::simple::ManhattanMetric",
        ],
    ),
    dict(
        name="td-scoredpoint",
        klass="typedep",
        crate="segment",
        expect="graph",
        confidence="high",
        q="Which scoring/fusion functions in `segment` return or take `segment::types::ScoredPoint`?",
        anchors=[_named("score_fusion"), _named("rrf_scoring")],
        dependents=[
            "segment::common::reciprocal_rank_fusion::rrf_scoring",
            "segment::common::score_fusion::score_fusion",
        ],
    ),
    # ===================== B. COLLISION / RESOLUTION (6, graph resolves) =====================
    dict(
        name="col-pl-sparse",
        klass="collision",
        crate="sparse",
        expect="graph",
        confidence="high",
        q="I'm storing sparse vectors and need the posting-list type built for them. There are multiple "
        "`PostingList` types here — which one do I use, and where is it defined?",
        anchors=[
            {"basename": "posting_list.rs", "line": 12, "symbol": "PostingList", "crate": "sparse"}
        ],
    ),
    dict(
        name="col-pl-general",
        klass="collision",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="I want the general compressed posting list (not the sparse-index one) — which `PostingList`, and "
        "where is it defined?",
        anchors=[
            {
                "basename": "posting_list.rs",
                "line": 27,
                "symbol": "PostingList",
                "crate": "posting_list",
            }
        ],
    ),
    dict(
        name="col-pb-sparse",
        klass="collision",
        crate="sparse",
        expect="graph",
        confidence="high",
        q="Building posting lists for sparse vectors — which `PostingBuilder` do I use, and where is it?",
        anchors=[
            {
                "basename": "posting_list.rs",
                "line": 117,
                "symbol": "PostingBuilder",
                "crate": "sparse",
            }
        ],
    ),
    dict(
        name="col-pb-general",
        klass="collision",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="Which `PostingBuilder` builds lists in the general `posting_list` crate, and where is it defined?",
        anchors=[
            {
                "basename": "builder.rs",
                "line": 11,
                "symbol": "PostingBuilder",
                "crate": "posting_list",
            }
        ],
    ),
    dict(
        name="col-pe-sparse",
        klass="collision",
        crate="sparse",
        expect="graph",
        confidence="high",
        q="When I iterate a sparse posting list, what element type do I get back, and where is it defined?",
        anchors=[
            {
                "basename": "posting_list_common.rs",
                "line": 19,
                "symbol": "PostingElement",
                "crate": "sparse",
            }
        ],
    ),
    dict(
        name="col-pe-general",
        klass="collision",
        crate="posting_list",
        expect="graph",
        confidence="high",
        q="In the general `posting_list` crate, what is the element type of a posting list, and where is it?",
        anchors=[
            {
                "basename": "posting_list.rs",
                "line": 52,
                "symbol": "PostingElement",
                "crate": "posting_list",
            }
        ],
    ),
    # ===================== C. PRIVATE-INTERNALS BOUNDARY (5, graph LOSES -> v2 + fairness floor) =====================
    dict(
        name="pv-compressed-size",
        klass="private",
        crate="posting_list",
        expect="grep",
        confidence="high",
        q="I want a posting list's compressed size in bytes. Is there already an internal helper that "
        "computes the compressed size of one encoded chunk I can follow?",
        anchors=[{"basename": "posting_list.rs", "line": 72, "symbol": "get_compressed_size"}],
    ),
    dict(
        name="pv-search-ge",
        klass="private",
        crate="posting_list",
        expect="grep",
        confidence="high",
        q="When the visitor skips ahead during a merge, where's the routine that searches for the first "
        "element with id greater than or equal to a target?",
        anchors=[{"basename": "visitor.rs", "line": 53, "symbol": "search_greater_or_equal"}],
    ),
    dict(
        name="pv-process-last",
        klass="private",
        crate="sparse",
        expect="grep",
        confidence="high",
        q="In sparse search, once all but one of the active lists are exhausted, where's the specialized path "
        "that finishes scoring the remainder?",
        anchors=[
            {
                "basename": "search_context.rs",
                "line": 198,
                "symbol": "process_last_posting_list",
                "crate": "sparse",
            }
        ],
    ),
    dict(
        name="pv-promote-longest",
        klass="private",
        crate="sparse",
        expect="grep",
        confidence="high",
        q="In the sparse search context, where's the routine that reorders the active lists so the largest one "
        "is handled first?",
        anchors=[
            {
                "basename": "search_context.rs",
                "line": 240,
                "symbol": "promote_longest_posting_lists_to_the_front",
                "crate": "sparse",
            }
        ],
    ),
    dict(
        name="pv-tracker-open",
        klass="private",
        crate="gridstore",
        expect="grep",
        confidence="high",
        q="In gridstore, where are the open options for the tracker file configured — random access, "
        "no populate?",
        anchors=[
            {
                "basename": "tracker.rs",
                "line": 24,
                "symbol": "tracker_open_options",
                "crate": "gridstore",
            }
        ],
    ),
    # ===================== D. CONTROL (4, both win — unique public names) =====================
    dict(
        name="ctl-view",
        klass="control",
        crate="posting_list",
        expect="both",
        confidence="high",
        q="What non-owning view type lets me borrow a `posting_list::PostingList` without copying, and where is it defined?",
        anchors=[
            {
                "basename": "view.rs",
                "line": 16,
                "symbol": "PostingListView",
                "crate": "posting_list",
            }
        ],
    ),
    dict(
        name="ctl-distancetype",
        klass="control",
        crate="quantization",
        expect="both",
        confidence="high",
        q="In `quantization`, what type represents the distance metric for encoded vectors, and where is it defined?",
        anchors=[
            {
                "basename": "encoded_vectors.rs",
                "line": 13,
                "symbol": "DistanceType",
                "crate": "quantization",
            }
        ],
    ),
    dict(
        name="ctl-geopoint",
        klass="control",
        crate="segment",
        expect="both",
        confidence="high",
        q="Where is `segment`'s `GeoPoint` type defined?",
        anchors=[{"basename": "types.rs", "line": 1907, "symbol": "GeoPoint", "crate": "segment"}],
    ),
    dict(
        name="ctl-gridstoreerror",
        klass="control",
        crate="gridstore",
        expect="both",
        confidence="high",
        q="What is gridstore's top-level error type called, and where is it defined?",
        anchors=[
            {"basename": "error.rs", "line": 7, "symbol": "GridstoreError", "crate": "gridstore"}
        ],
    ),
]

# --- Honest sub-classing (peer review FM1/FM5): split the type-dep headline by HOW the graph wins. ---
# capability  = no clean grep pattern (RETURNS/TAKES/HAS_FIELD); grep degrades / goes noisy -> accuracy win.
# completeness = trait-implementor lookups; grep CAN find direct `impl Trait for X`, so the graph win is
#                one-call completeness + no false positives (+ cross-crate). Report these separately; do NOT
#                bank them as accuracy wins over grep.
_COMPLETENESS = {
    "td-valuehandler",
    "td-encodedvectors",
    "td-idtracker",
    "td-vectorindex",
    "td-queryscorer",
    "td-vectorstorage",
}
_CROSS_CRATE = {
    "td-encodedvectors",
    "td-vectorparameters",
    "td-encodingerror",
}  # dependent lives in another crate
# Honest framing (eval audit 2026-06-28): every question carries `advantage` = the graph's REAL edge —
# never single-shot accuracy. typedep capability -> efficiency, typedep impls -> completeness, collision ->
# efficiency (noise-reduction), private -> boundary (grep wins; v2), control -> parity (both win).
_ADV = {"collision": "efficiency", "private": "boundary", "control": "parity"}
for _q in GOLD:
    if _q["klass"] == "typedep":
        _q["win"] = "completeness" if _q["name"] in _COMPLETENESS else "capability"
        _q["cross_crate"] = _q["name"] in _CROSS_CRATE
        _q["advantage"] = _q["win"]  # "capability" (efficiency/reliability) or "completeness"
    else:
        _q["advantage"] = _ADV[_q["klass"]]
