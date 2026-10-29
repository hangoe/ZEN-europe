"""Unit tests for the sector codes of the EEA GHG inventory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from zen_europe.datasets.datasets.energy_system.eea_ghg_inventory import (
    CHEMICALS_SECTORS,
    SECTOR_CODES,
    EEAGreenhouseGasInventory,
)

MODELS_PATH = Path(__file__).parents[2] / "data" / "models.yaml"


def _inventory(data: pd.DataFrame | None = None) -> EEAGreenhouseGasInventory:
    """An inventory that is not loaded, as constructing one downloads the data."""
    inventory = EEAGreenhouseGasInventory.__new__(EEAGreenhouseGasInventory)
    if data is not None:
        inventory._data = data
    return inventory


def _default_sectors() -> list[str]:
    models = yaml.safe_load(MODELS_PATH.read_text())
    return models["defaults"]["settings"]["structure"]["set_sectors"]


@pytest.mark.parametrize(
    "sectors",
    [_default_sectors(), list(SECTOR_CODES) + CHEMICALS_SECTORS],
    ids=["default", "all"],
)
def test_sector_codes_are_unique(sectors: list[str]) -> None:
    codes = _inventory().get_sector_codes(sectors)
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize(
    "sectors",
    [_default_sectors(), list(SECTOR_CODES) + CHEMICALS_SECTORS],
    ids=["default", "all"],
)
def test_no_code_nested_in_another(sectors: list[str]) -> None:
    """A code below a selected code, such as 2.A.3 below 2.A, is counted twice."""
    codes = _inventory().get_sector_codes(sectors)
    nested = [
        (child, parent)
        for child in codes
        for parent in codes
        if child.startswith(parent + ".")
    ]
    assert not nested


def test_select_rejects_duplicate_codes() -> None:
    index = pd.MultiIndex.from_tuples(
        [("2.A", "DE")], names=["sector_code", "node"]
    )
    inventory = _inventory(pd.DataFrame({2022: [1.0]}, index=index))
    with pytest.raises(ValueError, match="duplicates"):
        inventory._select(["2.A", "2.A"], ["DE"])
