from rigor_api.knowledge_candidate_context_routes import (
    CANDIDATE_PROBLEM_VISIBILITY_SQL,
    VERIFIED_RUNTIME_SQL,
)


def test_candidate_context_hides_statement_backed_metadata_review_content() -> None:
    assert "publication_status='published'" in CANDIDATE_PROBLEM_VISIBILITY_SQL
    assert "publication_status='metadata_only'" in CANDIDATE_PROBLEM_VISIBILITY_SQL
    assert "length(trim(COALESCE(p.description, ''))) = 0" in CANDIDATE_PROBLEM_VISIBILITY_SQL


def test_candidate_context_runtime_target_requires_verified_current_version() -> None:
    assert "knowledge_problem_runtime_links" in VERIFIED_RUNTIME_SQL
    assert "link_status='verified'" in VERIFIED_RUNTIME_SQL
    assert "current_published_version_id" in VERIFIED_RUNTIME_SQL
    assert "runtime_version.state='published'::content_state" in VERIFIED_RUNTIME_SQL


def test_candidate_context_does_not_use_executable_solution_as_runtime_gate() -> None:
    assert "knowledge_solutions" not in VERIFIED_RUNTIME_SQL
    assert "is_executable" not in VERIFIED_RUNTIME_SQL
