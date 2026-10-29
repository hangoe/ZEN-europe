"""Unit tests for the UK paper and food emissions of the ONS."""

from __future__ import annotations

from zen_europe.datasets.datasets.energy_system.desnz_ghg_inventory import (
    CHEMICALS_SECTORS,
)
from zen_europe.datasets.datasets.energy_system.ons_industry_emissions import (
    ONSIndustryEmissions,
)

from .conftest import RAW_DATA_PATH


def test_paper_and_food_without_chemicals() -> None:
    emissions = ONSIndustryEmissions(RAW_DATA_PATH).get_emissions_sectors(
        ["paper", "food"]
    )
    assert len(emissions) == 2
    assert (emissions > 0).all().all()


def test_no_double_counting_with_chemicals() -> None:
    """With the chemicals sectors, the DESNZ "Other industrial combustion" already
    holds the paper and food combustion."""
    emissions = ONSIndustryEmissions(RAW_DATA_PATH).get_emissions_sectors(
        ["paper", "food", *CHEMICALS_SECTORS]
    )
    assert emissions.empty
