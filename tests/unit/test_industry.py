"""Unit tests for the datasets and collections of the industry heat sectors."""

# TODO: check with Christoph whether this test file can be removed.

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
from zen_europe.datasets.datasets.carrier.jrc_bat_paper import JRCBATPaper
from zen_europe.datasets.datasets.carrier.rehfeldt2017 import Rehfeldt2017
from zen_europe.datasets.datasets.carrier.wolf2017 import Wolf2017
from zen_europe.datasets.datasets.financial.ECB import ECBInflation
from zen_europe.datasets.datasets.technology.brown2018 import Brown2018
from zen_europe.datasets.datasets.technology.dsm_literature_review import (
    DSMLiteratureReview,
)
from zen_europe.datasets.datasets.technology.jrc_eu_times_industry import (
    JRCEUTIMESIndustry,
)
from zen_europe.utils.constants import Constants
from zen_europe.utils.industry import DATA_YEAR, SECTORS
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


def test_heat_bands_are_useful_heat(production: IndustryProductionData) -> None:
    """The heat bands are the final energy below 200 °C times the reference boiler
    efficiency; the fuel above 200 °C stays final energy."""
    efficiency = production._assumptions.get_value("reference_boiler_efficiency")
    parameters = production._sector_parameters
    final_heat = parameters["fuel_total"] - parameters["fuel"]
    heat = parameters["heat_0_100"] + parameters["heat_100_200"]
    assert heat.to_numpy() == pytest.approx((final_heat * efficiency).to_numpy())


def test_fuel_shares(production: IndustryProductionData) -> None:
    for sector in SECTORS:
        shares = production.calculate_fuel_shares(sector)
        assert shares.sum() == pytest.approx(1)
        assert (shares > 0).all()


def test_kiln_fuel_only_for_glass_and_ceramic(
    production: IndustryProductionData,
) -> None:
    glass = production.calculate_fuel_intensity("glass").index
    assert "kiln_fuel_glass" in glass and "natural_gas" not in glass
    # 2.6 % of the ceramic kiln gas cannot switch fuel
    ceramic = production.calculate_fuel_intensity("ceramic").index
    assert {"kiln_fuel_ceramic", "natural_gas"} <= set(ceramic)
    for sector in ("paper", "food"):
        assert not any(
            c.startswith("kiln_fuel")
            for c in production.calculate_fuel_intensity(sector).index
        )


def test_demand_of_nodes_without_jrc_idees(production: IndustryProductionData) -> None:
    glass = production.calculate_demand("glass", NODES)
    assert glass["CH"] == glass["AT"] and glass["NO"] == glass["FI"]
    paper = production.calculate_demand("paper", NODES)
    consumption = JRCBATPaper(RAW_DATA_PATH).get_consumption()
    hours = Constants.HOURS_PER_YEAR
    assert paper["UK"] == pytest.approx(consumption["UK"] * 1000 / hours)


def test_demand_is_physical_output(production: IndustryProductionData) -> None:
    """Demand over the year equals the JRC-IDEES physical output (glass, paper)."""
    idees = production.data["jrc_idees"]
    year = DATA_YEAR
    for sector in ("glass", "paper"):
        output = idees.get_industry_physical_output(sector, year)  # type: ignore[attr-defined]
        nodes = [n for n in output.index if n in NODES]
        demand = production.calculate_demand(sector, NODES)[nodes]
        assert demand.sum() * Constants.HOURS_PER_YEAR / 1000 == pytest.approx(
            output[nodes].sum()
        )


def test_capacity_existing_has_headroom(production: IndustryProductionData) -> None:
    """Glass and paper plants have installed capacity above today's production; the
    other sectors and nodes have the assumed capacity utilisation."""
    capacity = production._calculate_capacity(NODES)
    for sector in ("glass", "paper"):
        demand = production.calculate_demand(sector, NODES)
        assert (capacity[sector] >= demand - 1e-9).all()
        assert 1.1 < capacity[sector].sum() / demand.sum() < 1.4
    utilisation = production._assumptions.get_value("capacity_utilisation")
    bat_nodes = list(JRCBATPaper(RAW_DATA_PATH).get_consumption().index)
    for sector, nodes in [
        ("ceramic", list(NODES)),
        ("food", list(NODES)),
        ("paper", bat_nodes),
    ]:
        demand = production.calculate_demand(sector, NODES)[nodes]
        assert capacity.loc[nodes, sector].to_numpy() == pytest.approx(
            (demand / utilisation).to_numpy()
        )


def test_kiln_fuel_capacity_matches_demand(
    heat_supply: IndustryHeatSupply, production: IndustryProductionData
) -> None:
    """Existing kiln natural gas capacity and kiln fuel limit share one basis."""
    for sector in ("glass", "ceramic"):
        intensity = production.calculate_fuel_intensity(sector)[f"kiln_fuel_{sector}"]
        assert (
            production.calculate_production(sector, NODES) * intensity
        ).to_numpy() == pytest.approx(
            (production.calculate_demand(sector, NODES) * intensity).to_numpy()
        )


def test_boiler_capacity_matches_sector_demand(
    heat_supply: IndustryHeatSupply, production: IndustryProductionData
) -> None:
    capacity = heat_supply._calculate_boiler_capacity(NODES)
    for sector in SECTORS:
        demand = (
            production.calculate_demand(sector, NODES)
            * production.calculate_energy_intensity(sector)["heat"]
        )
        assert capacity.loc[sector].sum(axis=1).to_numpy() == pytest.approx(
            demand.reindex(capacity.loc[sector].index).to_numpy()
        )


def test_boiler_fuel_mix_is_not_district_heating(
    heat_supply: IndustryHeatSupply,
) -> None:
    """Existing boilers follow the sectors' own fuel mix: no electrode boilers,
    waste only in paper (outside CH, which uses the BFE mix) and a small waste
    share overall."""
    capacity = heat_supply._calculate_boiler_capacity(NODES)
    assert (capacity["electrode"] == 0).all()
    for sector in ("glass", "ceramic", "food"):
        assert (capacity.loc[sector, "waste"].drop("CH") == 0).all()
    total = capacity.groupby(level="node").sum()
    waste_share = total["waste"] / total.sum(axis=1)
    for node in ("DE", "SE"):
        assert waste_share[node] < 0.10


def test_boiler_fuel_mix_of_ch_is_bfe(heat_supply: IndustryHeatSupply) -> None:
    shares = heat_supply._calculate_sector_fuel_shares(NODES)
    bfe = heat_supply.data["bfe_industry"].get_fuel_consumption(DATA_YEAR)
    expected = bfe.reindex(shares.columns, fill_value=0.0)
    expected = expected / expected.sum()
    for sector in SECTORS:
        assert shares.loc[(sector, "CH")].to_numpy() == pytest.approx(
            expected.to_numpy()
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
        reference_year - 1
    )
    vintages = format_capacity_existing(
        calculate_capacity_addition_from_cumulative(capacity, element)  # type: ignore[arg-type]
    )
    years = vintages.index.get_level_values("year_construction")
    assert years.max() == reference_year - 1
    assert vintages.groupby(level="node").sum()["DE"] == pytest.approx(
        capacity.loc["DE", reference_year - 1]
    )


def test_costs_are_in_price_year_euro(
    production: IndustryProductionData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production costs are inflated to `cost.price_year`, as all other costs, and
    do not depend on `time.reference_year`."""

    def costs(price_year: int, reference_year: int) -> pd.DataFrame:
        # the collection is a singleton: swap its settings and drop cached costs
        settings = Settings.model_validate(
            {
                "cost": {"price_year": price_year},
                "time": {"reference_year": reference_year},
            }
        )
        monkeypatch.setattr(production, "settings", settings)
        production.__dict__.pop("_costs", None)
        return production._costs

    try:
        base = costs(2022, 2022)
        pd.testing.assert_frame_equal(costs(2022, 2020), base)
        inflated = costs(2025, 2022)
    finally:
        monkeypatch.undo()
        production.__dict__.pop("_costs", None)
    inflation = ECBInflation(RAW_DATA_PATH).get_inflation_rate(2022, 2025)
    for sector in ("glass", "food"):
        assert inflated.at[sector, "capex"] == pytest.approx(
            base.at[sector, "capex"] * inflation, rel=1e-3
        )
    assert inflated.at["glass", "lifetime"] == base.at["glass", "lifetime"]


def test_dsm_shiftability() -> None:
    review = DSMLiteratureReview(RAW_DATA_PATH)
    categories = review.get_categories()
    assert (categories["pessimistic"] <= categories["optimistic"]).all()

    def cost(carrier: str, shiftability: str) -> float:
        settings = Settings.model_validate(
            {"industry_flexibility": {"dsm_shiftability": shiftability}}
        )
        element = SimpleNamespace(carrier=carrier, settings=settings)
        return review._get_cost(element, "capex")  # type: ignore[arg-type]

    assert cost("ceramic", "optimistic") == 20.0
    assert cost("ceramic", "pessimistic") == 1000.0
    # energy basis: per GWh instead of per tonne
    assert cost("ammonia", "optimistic") == pytest.approx(
        20.0 / Constants.AMMONIA_GWH_PER_TON
    )


def test_tes_self_discharge_brown2018() -> None:
    brown = Brown2018(RAW_DATA_PATH)
    assert brown.data.at["hot water tank central", "tau_days"] == 180
    assert Brown2018.hourly_self_discharge(180) == pytest.approx(2.315e-4, rel=1e-3)
    assert Brown2018.hourly_self_discharge(3) == pytest.approx(0.013793, rel=1e-4)
    assert Brown2018.hourly_self_discharge(20 / 24) == pytest.approx(0.0488, rel=1e-3)
