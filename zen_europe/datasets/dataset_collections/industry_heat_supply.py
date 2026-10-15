from __future__ import annotations

import logging
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd
from zen_creator import Attribute, DatasetCollection
from zen_creator.datasets.datasets.metadata import SourceInformation

from zen_europe.datasets.dataset_collections.industry_production_data import (
    IDEES_EU,
    NODES_WITHOUT_IDEES,
    IndustryProductionData,
)
from zen_europe.datasets.dataset_collections.technology_cost_database import (
    TechnologyCostDatabase,
)
from zen_europe.datasets.datasets.carrier.bfe_industry import BFEIndustry
from zen_europe.datasets.datasets.carrier.eurostat_energy_balance_industry import (
    EurostatEnergyBalanceIndustry,
)
from zen_europe.datasets.datasets.carrier.jrc_idees_industry import JRCIDEESIndustry
from zen_europe.utils.industry import (
    BOILER_FUELS,
    HEAT_LEVELS,
    HEAT_SOURCES,
    SECTORS,
    kiln_fuel,
    model_nodes,
)
from zen_europe.utils.utils import (
    calculate_capacity_addition_from_cumulative,
    format_capacity_existing,
)

if TYPE_CHECKING:
    from zen_creator import Dataset, Element
    from zen_creator.utils.settings import Settings

logger = logging.getLogger(__name__)

# boilers whose fuel mix is fitted to the sectors' JRC-IDEES fuel mix
COMBUSTION_FUELS = [fuel for fuel in BOILER_FUELS if fuel != "electrode"]
# JRC-IDEES thermal carrier of each boiler fuel; biomass and waste are split by the
# node's biomass:waste heat production (combined carrier in JRC-IDEES)
IDEES_BOILER_FUELS = {
    "Natural gas and biogas": "natural_gas",
    "Solids": "coal",
    "Derived gases": "coal",
    "LPG": "oil",
    "Diesel oil and liquid biofuels": "oil",
    "Fuel oil": "oil",
    "Other liquids": "oil",
    "Refinery gas": "oil",
}
# iterative proportional fitting of the sectors' boiler fuel mix
FIT_SEED_FLOOR = 1e-3
FIT_MAX_ITERATIONS = 1000
FIT_TOLERANCE = 1e-10
# heat pump COP: Carnot efficiency, supply (band centre) and source temperature (K)
CARNOT_EFFICIENCY = 0.5
SUPPLY_TEMPERATURE = {"0_100": 348.15, "100_150": 398.15, "150_200": 448.15}
SOURCE_TEMPERATURE = {"waste_heat": 323.15, "water": 288.15}
# waste-heat recovery (heat exchangers, piping) on top of the heat pump, Euro/kW:
# between 1,234 and 1,645 Euro/kW in Stark et al. (2025), Joule 9, 102157, Table 2
WASTE_HEAT_RECOVERY_CAPEX = 1500.0


class IndustryHeatSupply(DatasetCollection):
    """Existing capacities and limits of the industry heat supply technologies."""

    name = "industry_heat_supply"

    def __init__(self, settings: Settings, source_path: Path | str):
        self.settings = settings
        super().__init__(source_path=source_path)

    def _get_data(self) -> dict[str, Dataset[Any] | DatasetCollection]:
        """Load all available data sources."""
        if self.source_path is None:
            raise ValueError("source_path must be set to load the dataset collection.")
        return {
            "industry_production_data": IndustryProductionData(
                self.settings, self.source_path
            ),
            "eurostat_energy_balance_industry": EurostatEnergyBalanceIndustry(
                self.source_path
            ),
            "bfe_industry": BFEIndustry(self.source_path),
            "jrc_idees_industry": JRCIDEESIndustry(self.source_path),
            "technology_cost_database": TechnologyCostDatabase(
                self.settings, self.source_path
            ),
        }

    @property
    def _production_data(self) -> IndustryProductionData:
        return cast(IndustryProductionData, self.data["industry_production_data"])

    # ---------- boilers ----------

    def get_capacity_existing_boiler(self, element: Element) -> Attribute:
        """
        Get the existing capacity of an industrial boiler.

        The sectors' heat demand is split by fuel such that every fuel sums to the
        node's industrial heat production mix (Eurostat, BFE for CH) and every
        sector keeps its JRC-IDEES fuel mix as closely as possible.
        """
        capacity = self._calculate_boiler_capacity(model_nodes(element)).loc[
            element.sector, element.fuel]
        # drop the smallest boilers of a node
        capacity = capacity.where(
            capacity >= self.settings.industry.min_boiler_capacity, 0.0)
        return element.capacity_existing.set_data(
            default_value=0.0,
            unit="GW",
            df=self._format_capacity_existing(capacity, element),
            source=SourceInformation(
                description=(
                    "The existing boiler capacity equals the sector's heat demand "
                    "(100-200 °C), split by fuel with an iterative proportional fit "
                    "of the sectors' JRC-IDEES fuel mix to the node's gross heat "
                    "production per fuel (Eurostat, BFE for CH). Boilers below "
                    f"{self.settings.industry.min_boiler_capacity} GW per node are "
                    "dropped; the capacity is assumed to be built evenly over the "
                    "lifetime of the technology."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- heat pumps ----------

    def get_conversion_factor_heat_pump(self, element: Element) -> Attribute:
        """Get the electricity per heat, from a fraction of the Carnot COP."""
        supply = SUPPLY_TEMPERATURE[element.temp_level]
        source = SOURCE_TEMPERATURE[element.heat_source]
        cop = round(CARNOT_EFFICIENCY * supply / (supply - source), 4)
        return element.conversion_factor.set_data(
            default_value=[
                {"electricity": {"default_value": round(1.0 / cop, 12), "unit": "GW/GW"}}
            ],
            source=SourceInformation(
                description=(
                    f"The COP of {cop} is {CARNOT_EFFICIENCY:.0%} of the Carnot COP "
                    f"between the source ({source - 273.15:.0f} °C) and the centre "
                    f"of the temperature band ({supply - 273.15:.0f} °C)."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capex_specific_conversion_heat_pump(self, element: Element) -> Attribute:
        """Get the DEA investment cost, plus waste-heat recovery for waste-heat heat
        pumps."""
        tech_db = cast(TechnologyCostDatabase, self.data["technology_cost_database"])
        capex = tech_db.get_capex_specific_conversion(
            element, proxy_element_name=element.cost_proxy
        )
        if element.heat_source != "waste_heat":
            return capex
        return capex.set_data(
            default_value=capex.default_value + WASTE_HEAT_RECOVERY_CAPEX,
            df=None if capex.df is None else capex.df + WASTE_HEAT_RECOVERY_CAPEX,
            source=SourceInformation(
                description=(
                    f"The DEA investment cost of '{element.cost_proxy}' plus "
                    f"{WASTE_HEAT_RECOVERY_CAPEX} Euro/kW for the waste-heat recovery "
                    "(Stark et al. (2025), Joule 9, 102157, Table 2)."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capacity_limit_heat_pump(self, element: Element) -> Attribute:
        """Get the first-year cap (share of band demand) and, for waste heat, the
        sector's waste heat in the band."""
        nodes = pd.Index(model_nodes(element), name="node")
        years = pd.Index(self.settings.time.years, name="year")
        limit = pd.Series(np.inf, index=nodes)
        description = ""
        if element.heat_source == "waste_heat":
            production = self._production_data
            sector = element.sector
            heat = production.calculate_heat_conversion_factors(sector)
            share = heat[element.temp_level] / heat[list(HEAT_LEVELS)].sum()
            fuel = production.calculate_energy_intensity(sector)["fuel"]
            waste_heat = production.calculate_production(
                sector, tuple(nodes)) * fuel * share
            limit = waste_heat.reindex(nodes, fill_value=0.0)
            description = (
                "Waste heat of processes > 200 °C (their fuel demand), split by band "
                "heat demand. "
            )
        first_share = self.settings.industry.hp_share_first_year
        demand = self._calculate_band_demand(tuple(nodes)).loc[
            (element.sector, element.temp_level)]
        first_year = demand.reindex(nodes, fill_value=0.0) * first_share / len(
            HEAT_SOURCES)
        limit = pd.DataFrame({year: limit for year in years})
        limit[years[0]] = np.minimum(limit[years[0]], first_year)
        return element.capacity_limit.set_data(
            default_value=np.inf,
            unit="GW",
            df=limit.stack().rename_axis(["node", "year"]).rename(
                "capacity_limit").to_frame(),
            source=SourceInformation(
                description=(
                    description
                    + f"{years[0]}: at most {first_share:.0%} of band demand per node, "
                    "split by heat source."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capacity_addition_unbounded_heat_pump(self, element: Element) -> Attribute:
        """Get the seed: annual DH heat pump build-out, split by sector-band demand
        share, heat source and node."""
        fleet = float(
            element.model.elements["heat_pump_DH"].capacity_existing.df.squeeze().sum()
        )
        nodes = model_nodes(element)
        demand = self._calculate_band_demand(nodes).sum(axis=1)
        share = demand[element.sector, element.temp_level] / demand.sum()
        heat_sources = len(HEAT_SOURCES)
        interval = self.settings.time.interval_between_years
        seed_years = self.settings.industry.hp_seed_years
        return element.capacity_addition_unbounded.set_data(
            default_value=(
                fleet / seed_years * interval * share / heat_sources / len(nodes)),
            unit="GW",
            source=SourceInformation(
                description=(
                    f"Annual build-out of the DH heat pumps (fleet / {seed_years} yr) "
                    "per period, split by sector-band demand share, heat source and "
                    "node, see docs, 'Diffusion'."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- temperature cascade ----------

    def get_capacity_existing_temp_conversion(self, element: Element) -> Attribute:
        """Get today's heat flow down the cascade: all lower bands are supplied by
        boilers."""
        capacity = self._calculate_heat_demand(
            element.sector, element.served_levels, model_nodes(element))
        return element.capacity_existing.set_data(
            default_value=0.0,
            unit="GW",
            df=self._format_capacity_existing(capacity, element),
            source=SourceInformation(
                description=(
                    "The existing capacity equals the heat demand of the lower "
                    "bands, which today's boilers supply."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capacity_limit_temp_conversion(self, element: Element) -> Attribute:
        """Get the heat demand of the lower bands times the capacity limit margin."""
        capacity = self._calculate_heat_demand(
            element.sector, element.served_levels, model_nodes(element))
        return self._set_capacity_limit(element, capacity)

    # ---------- thermal energy storage ----------

    def get_capacity_limit_tes(self, element: Element) -> Attribute:
        """Get the heat demand of the storage's band and all lower bands times the
        capacity limit margin, 0 at nodes without demand."""
        levels = HEAT_LEVELS[: HEAT_LEVELS.index(element.temp_level) + 1]
        nodes = model_nodes(element)
        demand = self._calculate_heat_demand(element.sector, levels, nodes)
        margin = self.settings.industry.capacity_limit_margin
        limit = (demand * margin).reindex(pd.Index(nodes, name="node")).fillna(0.0)
        return element.capacity_limit.set_data(
            default_value=np.inf,
            unit="GW",
            df=limit.rename("capacity_limit").to_frame(),
            source=SourceInformation(
                description=(
                    "The flat heat demand of the storage's band and all lower bands "
                    "(reachable via the temperature cascade) times the capacity limit "
                    f"margin of {margin}; 0 at nodes without demand."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- kiln fuel ----------

    def get_capacity_existing_kiln_fuel(self, element: Element) -> Attribute:
        """Get today's kiln natural gas demand; none for the alternative fuels."""
        if element.fuel != "natural_gas":
            return element.capacity_existing.set_data(
                default_value=0.0,
                unit="GW",
                source=SourceInformation(
                    description="There is no existing capacity of alternative kiln fuels.",
                    metadata=self.metadata,
                ),
            )
        production = self._production_data
        capacity = production.calculate_production(
            element.sector, model_nodes(element)) * self._kiln_fuel_intensity(element)
        return element.capacity_existing.set_data(
            default_value=0.0,
            unit="GW",
            df=self._format_capacity_existing(capacity, element),
            source=SourceInformation(
                description=(
                    "The existing capacity equals the kiln natural gas demand of "
                    "today's production."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capacity_limit_kiln_fuel(self, element: Element) -> Attribute:
        """Get the kiln fuel demand times the capacity limit margin, natural gas
        only."""
        if element.fuel != "natural_gas":
            return element.capacity_limit.set_data(
                default_value=np.inf,
                unit="GW",
                source=SourceInformation(
                    description="The alternative kiln fuels are not limited.",
                    metadata=self.metadata,
                ),
            )
        production = self._production_data
        demand = production.calculate_demand(
            element.sector, model_nodes(element)) * self._kiln_fuel_intensity(element)
        return self._set_capacity_limit(element, demand)

    # ---------- helpers ----------

    @staticmethod
    def _format_capacity_existing(capacity: pd.Series, element: Element) -> pd.Series:
        """Spread today's capacity over its construction years, as for all other
        technologies."""
        capacity = capacity.to_frame(element.settings.time.reference_year - 1)
        capacity = calculate_capacity_addition_from_cumulative(capacity, element)
        return format_capacity_existing(capacity)

    def _set_capacity_limit(self, element: Element, demand: pd.Series) -> Attribute:
        """Limit the zero-cost pass-through technologies, see docs, 'Diffusion'."""
        margin = self.settings.industry.capacity_limit_margin
        limit = (demand * margin).rename("capacity_limit")
        return element.capacity_limit.set_data(
            default_value=np.inf,
            unit="GW",
            df=limit.to_frame(),
            source=SourceInformation(
                description=(
                    f"The flat demand times the capacity limit margin of {margin}, "
                    "see docs, 'Diffusion'."
                ),
                metadata=self.metadata,
            ),
        )

    def _kiln_fuel_intensity(self, element: Element) -> float:
        return self._production_data.calculate_fuel_intensity(element.sector)[
            kiln_fuel(element.sector)
        ]

    def _calculate_heat_demand(
        self, sector: str, levels: tuple[str, ...], nodes: tuple[str, ...]
    ) -> pd.Series:
        """Heat demand (GW) of the sector's products in the given bands."""
        return self._calculate_band_demand(nodes).loc[sector].loc[list(levels)].sum()

    @cache
    def _calculate_band_demand(self, nodes: tuple[str, ...]) -> pd.DataFrame:
        """Heat demand (GW) per sector and band (rows) and node (columns)."""
        production = self._production_data
        demand = {
            (sector, level): production.calculate_demand(sector, nodes) * heat
            for sector in SECTORS
            for level, heat in production.calculate_heat_conversion_factors(
                sector).items()
        }
        return pd.DataFrame(demand).T.rename_axis(["sector", "level"])

    @cache
    def _calculate_boiler_capacity(self, nodes: tuple[str, ...]) -> pd.DataFrame:
        """
        Boiler capacity (GW) per sector and node (rows) and fuel (columns).

        The sectors' heat demand is split such that every fuel sums to the node's
        pooled capacity (Eurostat, BFE) and every sector to its own heat demand, with
        the sectors' JRC-IDEES fuel mix deciding who gets which fuel.
        """
        production = self._production_data
        # production capacity basis, as the heat carriers
        demand = pd.DataFrame({
            sector: production.calculate_demand(sector, nodes)
            * production.calculate_energy_intensity(sector)["heat"]
            for sector in SECTORS
        })  # node x sector
        total = demand.sum(axis=1)
        pooled = self._calculate_boiler_fuel_shares(nodes).mul(total, axis=0)
        # electrode boilers are split by the sectors' heat demand
        electrode = demand.div(total.where(total > 0), axis=0).fillna(0.0).mul(
            pooled["electrode"], axis=0)
        seed = self._calculate_initial_fuel_shares(pooled, nodes)
        capacity = {}
        for node in nodes:
            fitted = _fit_fuel_matrix(
                seed.xs(node, level="node"),
                demand.loc[node] - electrode.loc[node],
                pooled.loc[node, COMBUSTION_FUELS],
            )
            fitted["electrode"] = electrode.loc[node]
            capacity[node] = fitted
        capacity = pd.concat(capacity, names=["node", "sector"])
        return capacity.swaplevel().sort_index()[list(BOILER_FUELS)]

    def _calculate_boiler_fuel_shares(self, nodes: tuple[str, ...]) -> pd.DataFrame:
        """Fuel shares of the industrial heat production per node."""
        eurostat = cast(EurostatEnergyBalanceIndustry,
                        self.data["eurostat_energy_balance_industry"])
        bfe = cast(BFEIndustry, self.data["bfe_industry"])
        year = self.settings.industry.data_year
        heat = eurostat.get_heat_production(year).rename(
            columns={"electricity": "electrode"})
        heat = heat.reindex(
            index=list(nodes), columns=list(BOILER_FUELS), fill_value=0.0)
        # CH: fuel consumption of the BFE industry branches, no electrode boilers
        if "CH" in heat.index:
            heat.loc["CH"] = bfe.get_fuel_consumption(year).reindex(
                BOILER_FUELS, fill_value=0.0)
        total = heat.sum(axis=1)
        shares = heat.div(total.where(total > 0), axis=0)
        # nodes without heat production are assumed to burn natural gas
        shares.loc[total <= 0] = [float(fuel == "natural_gas") for fuel in BOILER_FUELS]
        return shares

    def _calculate_initial_fuel_shares(
        self, pooled: pd.DataFrame, nodes: tuple[str, ...]
    ) -> pd.DataFrame:
        """Combustion fuel mix per sector and node (JRC-IDEES, else EU27)."""
        idees = cast(JRCIDEESIndustry, self.data["jrc_idees_industry"])
        countries = [IDEES_EU if node in NODES_WITHOUT_IDEES else node for node in nodes]
        # waste share of the node's pooled biomass and waste capacity
        biomass_and_waste = pooled["biomass"] + pooled["waste"]
        waste_share = (pooled["waste"] / biomass_and_waste.where(biomass_and_waste > 0)
                       ).fillna(0.0)
        shares = {}
        for sector in SECTORS:
            thermal = idees.get_thermal_final_energy(
                sector, self.settings.industry.data_year).loc[countries]
            thermal.index = pd.Index(list(nodes), name="node")
            fuels = thermal.T.groupby(thermal.columns.map(IDEES_BOILER_FUELS)).sum().T
            fuels = fuels.reindex(columns=COMBUSTION_FUELS, fill_value=0.0)
            other = thermal.get("Biomass and waste", 0.0)
            fuels["biomass"] += other * (1.0 - waste_share)
            fuels["waste"] += other * waste_share
            total = fuels.sum(axis=1)
            fuels = fuels.div(total.where(total > 0), axis=0)
            # equal shares if the sector consumes no fuel at the node
            shares[sector] = fuels.fillna(1.0 / len(COMBUSTION_FUELS))
        return pd.concat(shares, names=["sector", "node"])


def _fit_fuel_matrix(
    seed: pd.DataFrame, row_totals: pd.Series, column_totals: pd.Series
) -> pd.DataFrame:
    """Scale `seed` (sector x fuel) to the row and column totals (iterative
    proportional fitting)."""
    seed = seed.loc[row_totals.index, column_totals.index]
    matrix = seed.to_numpy() + FIT_SEED_FLOOR
    rows_target = row_totals.to_numpy()
    columns_target = column_totals.to_numpy()
    tolerance = FIT_TOLERANCE * max(1.0, rows_target.sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        for _ in range(FIT_MAX_ITERATIONS):
            rows = matrix.sum(axis=1)
            matrix = np.where(rows[:, None] > 0, matrix * (rows_target / rows)[:, None], 0.0)
            columns = matrix.sum(axis=0)
            matrix = np.where(columns > 0, matrix * columns_target / columns, 0.0)
            column_error = np.abs(columns - columns_target).max()
            row_error = np.abs(matrix.sum(axis=1) - rows_target).max()
            if max(column_error, row_error) <= tolerance:
                break
        else:
            logger.warning(
                f"Boiler fuel fit did not converge in {FIT_MAX_ITERATIONS} iterations.")
    return pd.DataFrame(matrix, index=seed.index, columns=seed.columns)
