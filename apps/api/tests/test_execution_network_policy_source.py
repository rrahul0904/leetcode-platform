from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_vpc_cni_network_policy_enforcement_is_enabled() -> None:
    source = (
        ROOT / "infra" / "terraform" / "modules" / "execution_eks" / "addons.tf"
    ).read_text(encoding="utf-8")

    assert 'each.value == "vpc-cni"' in source
    assert 'enableNetworkPolicy = "true"' in source
