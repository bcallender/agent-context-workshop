from context_workshop.graph.tools import q_blast_radius, q_neighborhood, q_public_api, q_search


def test_blast_radius_is_inbound_and_depth_bounded():
    cy, params = q_blast_radius("c::T", depth=3)
    assert params == {"qn": "c::T"}
    assert "<-[" in cy and "*1..3" in cy and "DISTINCT" in cy


def test_search_tokenizes_case_insensitively():
    cy, params = q_search("Posting", limit=5)
    assert params["tokens"] == ["posting"] and params["limit"] == 5
    assert "toLower" in cy and "CONTAINS" in cy and "ALL(" in cy
    # a phrase splits into tokens, so it can match a CamelCase symbol like DistanceMetric
    _, params2 = q_search("Distance Metric")
    assert params2["tokens"] == ["distance", "metric"]


def test_public_api_scopes_to_public_label_and_crate():
    cy, params = q_public_api("posting_list")
    assert params == {"crate": "posting_list"} and ":Public" in cy


def test_neighborhood_includes_limit_param():
    cy, params = q_neighborhood("c::MyType")
    assert "LIMIT" in cy and params["limit"] == 50
    cy2, params2 = q_neighborhood("c::MyType", limit=10)
    assert params2["limit"] == 10
