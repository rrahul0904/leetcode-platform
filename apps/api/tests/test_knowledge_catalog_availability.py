from rigor_api.knowledge_catalog_routes import derive_availability


def test_published_executable_problem_is_runnable() -> None:
    assert (
        derive_availability(
            "published",
            has_description=True,
            has_executable_solution=True,
        )
        == "runnable"
    )


def test_published_non_executable_problem_is_hosted() -> None:
    assert (
        derive_availability(
            "published",
            has_description=True,
            has_executable_solution=False,
        )
        == "hosted"
    )


def test_statement_backed_metadata_is_in_review() -> None:
    assert (
        derive_availability(
            "metadata_only",
            has_description=True,
            has_executable_solution=False,
        )
        == "in_review"
    )


def test_metadata_without_statement_is_reference_only() -> None:
    assert (
        derive_availability(
            "metadata_only",
            has_description=False,
            has_executable_solution=False,
        )
        == "reference_only"
    )


def test_unpublished_state_never_becomes_candidate_runnable() -> None:
    assert (
        derive_availability(
            "draft",
            has_description=True,
            has_executable_solution=True,
        )
        == "reference_only"
    )
