"""Unit tests for the datasets and collections of the industry heat sectors."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from zen_creator.utils.settings import Settings

import zen_europe.settings  # noqa: F401  # registers the settings categories
from zen_europe.datasets.dataset_collections.industry_heat_supply import (
    IndustryHeatSupply,
)
from zen_europe.datasets.dataset_collections.industry_production_data import (
    IndustryProductionData,
)
from zen_europe.datasets.datasets.carrier.rehfeldt2017 import Rehfeldt2017
from zen_europe.datasets.datasets.carrier.wolf2017 import Wolf2017
from zen_europe.datasets.datasets.technology.brown2018 import Brown2018
from zen_europe.datasets.datasets.technology.dsm_literature_review import (
    CATEGORIES,
    DSMLiteratureReview,
)
from zen_europe.datasets.datasets.technology.jrc_bat_paper import JRCBATPaper
from zen_europe.datasets.datasets.technology.jrc_eu_times_industry import (
    JRCEUTIMESIndustry,
)
from zen_europe.utils.constants import Constants
from zen_europe.utils.industry import SECTORS
from zen_europe.utils.utils import (
    calculate_capacity_addition_from_cumulative,
    format_capacity_existing,
)

from .conftest import RAW_DATA_PATH

NODES = tuple(Settings().region.set_nodes)


@pytest.fixture(scope="module")
def production() -> IndustryProductionData:
    return IndustryProductionData(Settings(), RAW_DATA_PATH)


@pytest.fixture(scope="module")
def heat_supply() -> IndustryHeatSupply:
    return IndustryHeatSupply(Settings(), RAW_DATA_PATH)


def test_activity_weights_sum_to_one() -> None:
    rehfeldt = Rehfeldt2017(RAW_DATA_PATH)
    for sector in SECTORS:
        assert rehfeldt.get_activity_weights(sector).sum() == pytest.approx(1)


def test_temperature_split_sums_to_one() -> None:
    split = Wolf2017(RAW_DATA_PATH).get_temperature_split()
    assert set(split.index) == set(SECTORS)
    assert split.sum(axis=1).to_numpy() == pytest.approx(1)
    assert split.loc["glass"].equals(split.loc["ceramic"])


def test_unknown_process_raises() -> None:
    with pytest.raises(ValueError):
        JRCEUTIMESIndustry(RAW_DATA_PATH).get_process_parameters("NOT_A_PROCESS")


def test_fuel_shares(production: IndustryProductionData) -> None:
    for sector in SECTORS:
        shares = production.calculate_fuel_shares(sector)
        assert shares.sum() == pytest.approx(1)
        assert (shares > 0).all()


def test_kiln_fuel_only_for_glass_and_ceramic(
    production: IndustryProductionData,
) -> None:
    glass = production.calculate_fuel_intensity("glass").index
    assert "fuel_to_kiln_glass" in glass and "natural_gas" not in glass
    # 2.6 % of the ceramic kiln gas cannot switch fuel
    ceramic = production.calculate_fuel_intensity("ceramic").index
    assert {"fuel_to_kiln_ceramic", "natural_gas"} <= set(ceramic)
    for sector in ("paper", "food"):
        assert not any(
            c.startswith("fuel_to_kiln")
            for c in production.calculate_fuel_intensity(sector).index
        )


def test_demand_of_nodes_without_jrc_idees(production: IndustryProductionData) -> None:
    glass = production.calculate_demand("glass", NODES)
    assert glass["CH"] == glass["AT"] and glass["NO"] == glass["FI"]
    paper = production.calculate_demand("paper", NODES)
    consumption = JRCBATPaper(RAW_DATA_PATH).get_consumption()
    hours = production.settings.industry.operating_hours
    assert paper["UK"] == pytest.approx(consumption["UK"] * 1000 / hours)


def test_boiler_capacity_matches_demand_and_fuel_totals(
    heat_supply: IndustryHeatSupply, production: IndustryProductionData
) -> None:
    capacity = heat_supply._calculate_boiler_capacity(NODES)
    demand = pd.DataFrame({
        s: production.calculate_demand(s, NODES)
        * production.calculate_energy_intensity(s)["heat"]
        for s in SECTORS
    })
    pooled = heat_supply._calculate_boiler_fuel_shares(NODES)
    for node in ("DE", "SE", "CH"):
        node_capacity = capacity.xs(node, level="node")
        assert node_capacity.sum(axis=1)[list(SECTORS)].to_numpy() == pytest.approx(
            demand.loc[node, list(SECTORS)].to_numpy()
        )
        assert node_capacity.sum().to_numpy() == pytest.approx(
            (demand.loc[node].sum() * pooled.loc[node])[node_capacity.columns].to_numpy()
        )


def test_capacity_existing_uses_shared_vintages(
    production: IndustryProductionData,
) -> None:
    """Industry capacities are spread over the same vintages as all other
    technologies."""
    reference_year = production.settings.time.reference_year
    element = SimpleNamespace(
        name="glass_production",
        sector="glass",
        settings=production.settings,
        lifetime=SimpleNamespace(default_value=20),
        construction_time=SimpleNamespace(default_value=0),
    )
    capacity = production._calculate_capacity(NODES)["glass"].to_frame(
        reference_year - 1)
    vintages = format_capacity_existing(
        calculate_capacity_addition_from_cumulative(capacity, element)  # type: ignore[arg-type]
    )
    years = vintages.index.get_level_values("year_construction")
    assert years.max() == reference_year - 1
    assert vintages.groupby(level="node").sum()["DE"] == pytest.approx(
        production.calculate_demand("glass", NODES)["DE"]
    )


def test_dsm_shiftability() -> None:
    review = DSMLiteratureReview(None)
    for categories in CATEGORIES.values():
        assert categories["pessimistic"] <= categories["optimistic"]

    def cost(carrier: str, shiftability: str) -> float:
        settings = Settings.model_validate(
            {"industry": {"dsm_shiftability": shiftability}}
        )
        element = SimpleNamespace(carrier=carrier, settings=settings)
        return review._get_cost(element, "capex")  # type: ignore[arg-type]

    assert cost("ceramic", "optimistic") == 20.0
    assert cost("ceramic", "pessimistic") == 1000.0
    # energy basis: per GWh instead of per tonne
    assert cost("ammonia", "optimistic") == pytest.approx(
        20.0 / Constants.AMMONIA_GWH_PER_TON)


def test_tes_self_discharge_brown2018() -> None:
    brown = Brown2018(RAW_DATA_PATH)
    assert brown.data.at["hot water tank decentral", "tau_days"] == 3
    assert Brown2018.hourly_self_discharge(3) == pytest.approx(0.013793, rel=1e-4)
    assert Brown2018.hourly_self_discharge(20 / 24) == pytest.approx(0.0488, rel=1e-3)
