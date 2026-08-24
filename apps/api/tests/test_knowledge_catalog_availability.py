from rigor_api.knowledge_catalog_routes import (
    AVAILABILITY_SQL,
    CANDIDATE_VISIBILITY_SQL,
    derive_availability,
)


def test_published_problem_requires_verified_runtime_link_to_be_runnable() -> None:
    assert (
        derive_availability(
            "published",
            has_verified_runtime_link=True,
        )
        == "runnable"
    )


def test_published_problem_without_verified_runtime_link_is_published_only() -> None:
    assert (
        derive_availability(
            "published",
            has_verified_runtime_link=False,
        )
        == "published"
    )


def test_metadata_only_problem_is_reference_only_to_candidate() -> None:
    assert (
        derive_availability(
            "metadata_only",
            has_verified_runtime_link=False,
        )
        == "reference_only"
    )


def test_unpublished_state_never_becomes_candidate_runnable() -> None:
    assert (
        derive_availability(
            "draft",
            has_verified_runtime_link=True,
        )
        == "reference_only"
    )


def test_runnable_sql_requires_verified_current_published_runtime_link() -> None:
    assert "knowledge_problem_runtime_links" in AVAILABILITY_SQL
    assert "link_status='verified'" in AVAILABILITY_SQL
    assert "current_published_version_id" in AVAILABILITY_SQL
    assert "runtime_version.state='published'::content_state" in AVAILABILITY_SQL
    assert "knowledge_solutions" not in AVAILABILITY_SQL


def test_candidate_visibility_excludes_statement_backed_review_metadata() -> None:
    assert "publication_status='published'" in CANDIDATE_VISIBILITY_SQL
    assert "publication_status='metadata_only'" in CANDIDATE_VISIBILITY_SQL
    assert "length(trim(COALESCE(p.description, ''))) = 0" in CANDIDATE_VISIBILITY_SQL
