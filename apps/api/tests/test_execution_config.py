from __future__ import annotations

import pytest
from pydantic import ValidationError

from rigor_api.config import Settings


@pytest.mark.parametrize("adapter", ["LOCAL_FUNCTIONAL", "LOCAL_DOCKER"])
def test_local_execution_is_allowed_only_for_local_development(adapter: str) -> None:
    settings = Settings(environment="development", execution_adapter=adapter)

    assert settings.execution_adapter == adapter


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("adapter", ["LOCAL_FUNCTIONAL", "LOCAL_DOCKER"])
def test_local_execution_is_rejected_for_deployable_environments(
    environment: str,
    adapter: str,
) -> None:
    with pytest.raises(ValidationError, match=f"{adapter} candidate execution is forbidden"):
        Settings(environment=environment, execution_adapter=adapter)


def test_isolated_execution_configuration_is_accepted_for_production() -> None:
    settings = Settings(environment="production", execution_adapter="KUBERNETES_JOB")

    assert settings.execution_adapter == "KUBERNETES_JOB"
