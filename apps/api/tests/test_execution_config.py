from __future__ import annotations

import pytest
from pydantic import ValidationError

from rigor_api.config import Settings


def test_local_execution_is_allowed_only_for_development() -> None:
    settings = Settings(environment="development", execution_adapter="LOCAL_FUNCTIONAL")

    assert settings.execution_adapter == "LOCAL_FUNCTIONAL"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_local_execution_is_rejected_for_deployable_environments(environment: str) -> None:
    with pytest.raises(ValidationError, match="LOCAL_FUNCTIONAL candidate execution is forbidden"):
        Settings(environment=environment, execution_adapter="LOCAL_FUNCTIONAL")


def test_isolated_execution_configuration_is_accepted_for_production() -> None:
    settings = Settings(environment="production", execution_adapter="KUBERNETES_JOB")

    assert settings.execution_adapter == "KUBERNETES_JOB"
