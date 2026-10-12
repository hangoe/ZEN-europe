from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from zen_creator import Attribute, DatasetCollection
from zen_creator.datasets.datasets.metadata import SourceInformation

from zen_europe.datasets.datasets.carrier.aidres_glass import AIDRESGlass
from zen_europe.datasets.datasets.carrier.faostat_food import FAOSTATFood
from zen_europe.datasets.datasets.carrier.jrc_idees_industry import JRCIDEESIndustry
from zen_europe.datasets.datasets.carrier.rehfeldt2017 import Rehfeldt2017
from zen_europe.datasets.datasets.carrier.wolf2017 import Wolf2017
from zen_europe.datasets.datasets.financial.dea import DEA
from zen_europe.datasets.datasets.financial.ECB import ECBInflation
from zen_europe.datasets.datasets.technology.jrc_bat_paper import JRCBATPaper
from zen_europe.datasets.datasets.technology.jrc_eu_times_industry import (
    BASE_YEAR,
    JRCEUTIMESIndustry,
)
from zen_europe.utils.constants import Constants
from zen_europe.utils.utils import (
    calculate_capacity_addition_from_cumulative,
    format_capacity_existing,
)

if TYPE_CHECKING:
    from zen_creator import Dataset, Element
    from zen_creator.utils.settings import Settings

SECTORS = ("glass", "ceramic", "paper", "food")
HEAT_LEVELS = ("0_100", "100_150", "150_200")
NODES_WITHOUT_IDEES = ("CH", "NO", "UK")
IDEES_EU = "EU27"
# proxy node and scaling factor of the nodes without JRC-IDEES data: CH as AT,
# NO as FI, UK as DE times the UK/DE population 2023 (69.9 M / 83.5 M)
PROXY_NODES = {"CH": ("AT", 1.0), "NO": ("FI", 1.0), "UK": ("DE", 69.9 / 83.5)}
# JRC-IDEES thermal carriers that are fuel inputs of the production technologies
FUELS = {
    "Natural gas and biogas": "natural_gas",
    "Solids": "hard_coal",
    "Biomass and waste": "biomass",
    "Other liquids": "oil",
}
# JRC-EU-TIMES processes of the glass routes and paper sub-processes
JRC_PROCESSES = {
    "glass": {
        "container": "IGHHOLLOW01",
        "flat": "IGFFLATGL01",
        "fibre": "IGFFLATGL01",
    },
    "paper": {
        "paper": "IPPHIGQUA01",
        "recovered_fibres": "IPPLOWQUA01",
        "chemical_pulp": "IPPPUPCHE01",
    },
}
# FAOSTAT item of each Rehfeldt (2017) food sub-process
FOOD_ITEMS = {
    "dairy": "Milk, Total",
    "meat_processing": "Meat, Total",
    "brewing": "Beer of barley, malted",
    "bread_bakery": "Wheat",
    "sugar": "Raw cane or beet sugar (centrifugal only)",
}
# process CO2 (t/t), see docs, "Production technologies"
CARBON_INTENSITY = {"glass": 0.1, "ceramic": 0.064234, "paper": 0.0, "food": 0.0}
# share of the kiln natural gas that can switch fuel, see docs, "Kiln fuel switching"
KILN_SWITCHABLE_SHARE = {"glass": 1.0, "ceramic": 46.26 / 47.49}
# Gardarsdottir et al. (2019) reference cement plant, EUR2014: proxy for ceramic costs
CERAMIC_PLANT = {"capacity_t_h": 120.65, "investment": 204e6, "price_year": 2014}
# literature capex of paper (Euro/(t/a)), see docs, "Paper"
PAPER_CAPEX = 700
# capex and fixed opex of food production (Euro/(t/a), BASE_YEAR prices)
FOOD_COSTS = {"capex": 300, "opex_fixed": 15}


class IndustryProductionData(DatasetCollection):
    """Production technologies, product demand and fuel mix of the industry sectors."""

    name = "industry_production_data"

    def __init__(self, settings: Settings, source_path: Path | str):
        self.settings = settings
        super().__init__(source_path=source_path)

    def _get_data(self) -> dict[str, Dataset[Any]]:
        """Load all available data sources."""
        if self.source_path is None:
            raise ValueError("source_path must be set to load the dataset collection.")
        return {
            "rehfeldt2017": Rehfeldt2017(self.source_path),
            "aidres_glass": AIDRESGlass(self.source_path),
            "wolf2017": Wolf2017(self.source_path),
            "jrc_idees_industry": JRCIDEESIndustry(self.source_path),
            "faostat_food": FAOSTATFood(self.source_path),
            "jrc_bat_paper": JRCBATPaper(self.source_path),
            "jrc_eu_times_industry": JRCEUTIMESIndustry(self.source_path),
            "dea": DEA(self.source_path),
            "ecb": ECBInflation(self.source_path),
        }

    # ---------- carriers ----------

    def get_demand(self, element: Element) -> Attribute:
        """
        Get the product demand of an industry sector.

        The demand equals today's production capacity at the plants' operating
        hours, so that today's plants run at full load.
        """
        return element.demand.set_data(
            default_value=0.0,
            unit="tproduct/h",
            df=self.calculate_demand(element.sector),
            source=SourceInformation(
                description=(
                    f"The {element.sector} demand equals today's production capacity "
                    f"at {self.settings.industry.operating_hours} operating hours per "
                    "year. The capacity is taken from JRC-IDEES (glass, paper), "
                    "derived from the JRC-IDEES thermal energy consumption and the "
                    "Rehfeldt et al. (2017) fuel intensity (ceramic), or from the "
                    "FAOSTAT production (food). Nodes without JRC-IDEES data use a "
                    "proxy node (CH as AT, NO as FI, UK as DE scaled by population); "
                    "for paper, their consumption from the JRC BAT reference "
                    "document is used."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- production technologies ----------

    def get_input_carrier(self, element: Element) -> Attribute:
        """Get the input carriers of a production technology: fuels, heat bands and
        electricity."""
        carriers = [
            *self._calculate_fuel_inputs(element.sector).index,
            *[element.heat_carrier(level) for level in self._active_heat_levels(element)],
            "electricity",
        ]
        return element.input_carrier.set_data(
            default_value=carriers,
            source=SourceInformation(
                description=(
                    "The fuels are the JRC-IDEES thermal energy carriers of the "
                    f"sector with a share of at least "
                    f"{self.settings.industry.fuel_share_cutoff:.0%}."
                ),
                metadata=self.metadata,
            ),
        )

    def get_conversion_factor(self, element: Element) -> Attribute:
        """
        Get the conversion factor of a production technology.

        The fuel (above 200 °C), heat (per temperature band) and electricity demand
        per tonne of product.
        """
        sector = element.sector
        energy = self.calculate_energy_intensity(sector)
        heat = self.calculate_heat_conversion_factors(sector)
        unit = "GW/(tproduct/h)"
        cf = [
            {carrier: {"default_value": value, "unit": unit}}
            for carrier, value in self.calculate_fuel_intensity(sector).items()
        ]
        cf.append(
            {"electricity": {"default_value": round(energy["electricity"], 12), "unit": unit}}
        )
        cf += [
            {element.heat_carrier(level): {"default_value": round(heat[level], 12), "unit": unit}}
            for level in self._active_heat_levels(element)
        ]
        return element.conversion_factor.set_data(
            default_value=cf,
            source=SourceInformation(
                description=(
                    "The energy intensity is the activity-weighted energy intensity of "
                    "the sector's sub-processes from Rehfeldt et al. (2017) (glass: "
                    "AIDRES (2023) routes, weighted by EU production share). Heat "
                    "below 200 °C is split into temperature bands with the Rehfeldt "
                    "temperature distribution and, for 100-200 °C, with Wolf (2017); "
                    "the rest is fuel, split by the JRC-IDEES fuel mix."
                ),
                metadata=self.metadata,
            ),
        )

    def get_capacity_existing(self, element: Element) -> Attribute:
        """Get the existing production capacity, built evenly over the lifetime."""
        capacity = self._capacity[element.sector]
        capacity = capacity.to_frame(element.settings.time.reference_year - 1)
        capacity = calculate_capacity_addition_from_cumulative(capacity, element)
        capacity = format_capacity_existing(capacity)
        return element.capacity_existing.set_data(
            default_value=0.0,
            unit="tproduct/h",
            df=capacity,
            source=SourceInformation(
                description=(
                    "The existing production capacity equals the product demand "
                    "(JRC-IDEES, FAOSTAT and JRC BAT, see demand), assumed to be "
                    "built evenly over the lifetime of the technology."
                ),
                metadata=self.metadata,
            ),
        )

    def get_lifetime(self, element: Element) -> Attribute:
        """Get the lifetime from JRC-EU-TIMES or the sector's cost proxy."""
        return element.lifetime.set_data(
            default_value=float(self._costs.at[element.sector, "lifetime"]),
            source=self._cost_source(element.sector),
        )

    def get_capex_specific_conversion(self, element: Element) -> Attribute:
        """Get the investment cost, see docs, "Production technologies"."""
        return element.capex_specific_conversion.set_data(
            default_value=float(self._costs.at[element.sector, "capex"]),
            unit="Euro/(tproduct/h)",
            source=self._cost_source(element.sector),
        )

    def get_opex_specific_fixed(self, element: Element) -> Attribute:
        """Get the fixed O&M cost."""
        return element.opex_specific_fixed.set_data(
            default_value=float(self._costs.at[element.sector, "opex_fixed"]),
            unit="Euro/(tproduct/h)",
            source=self._cost_source(element.sector),
        )

    def get_opex_specific_variable(self, element: Element) -> Attribute:
        """Get the variable O&M cost, without energy."""
        return element.opex_specific_variable.set_data(
            default_value=float(self._costs.at[element.sector, "opex_variable"]),
            unit="Euro/tproduct",
            source=self._cost_source(element.sector),
        )

    def get_carbon_intensity_technology(self, element: Element) -> Attribute:
        """Get the process CO2 emissions."""
        intensity = CARBON_INTENSITY[element.sector]
        return element.carbon_intensity_technology.set_data(
            default_value=float(intensity),
            unit="ton/tproduct",
            source=SourceInformation(
                description=(
                    f"The process CO2 emissions of {element.sector} production are "
                    f"{intensity} t per t of product, see docs, 'Production "
                    "technologies'."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- post-combustion capture ----------

    def get_conversion_factor_post_comb(self, element: Element) -> Attribute:
        """
        Get the conversion factor of the post-combustion capture of a sector.

        The capture unit is the one of cement_post_comb; its heat is supplied by the
        sector's natural gas and coal, split by the sector's fuel mix.
        """
        dea = cast(DEA, self.data["dea"])
        cement = {
            carrier: values["default_value"]
            for entry in dea.get_conversion_factor_cement_post_comb()
            for carrier, values in entry.items()
        }
        shares = self.calculate_fuel_shares(element.sector)
        heat_fuels = shares[shares.index.isin(["natural_gas", "hard_coal"])]
        heat_fuels = heat_fuels / heat_fuels.sum()
        unit = "GW/(kilotCO2/hour)"
        cf = [
            {
                carrier: {
                    "default_value": round(cement["fuel_for_cement"] * share, 12),
                    "unit": unit,
                }
            }
            for carrier, share in heat_fuels.items()
        ]
        cf += [
            {carrier: {"default_value": cement[carrier], "unit": unit}}
            for carrier in ("electricity", "district_heat")
        ]
        return element.conversion_factor.set_data(
            default_value=cf,
            source=SourceInformation(
                description=(
                    "The capture unit is the DEA post-combustion capture unit of "
                    "cement_post_comb. Its heat demand is supplied by the sector's "
                    "natural gas and coal, split by the sector's JRC-IDEES fuel mix."
                ),
                metadata=self.metadata,
            ),
        )

    def get_retrofit_flow_coupling_factor(self, element: Element) -> Attribute:
        """Get the captured process CO2 per tonne of product."""
        dea = cast(DEA, self.data["dea"])
        capture_rate = dea.get_capture_rate_CCS()
        intensity = float(CARBON_INTENSITY[element.sector])
        return element.retrofit_flow_coupling_factor.set_data(
            default_value=round(intensity * capture_rate / 1000.0, 12),  # t -> kt
            unit="kilotCO2/tproduct",
            base_technology=f"{element.sector}_production",
            source=SourceInformation(
                description=(
                    f"The process emissions of {intensity} t CO2 per t of product "
                    f"times the DEA capture rate of {capture_rate:.0%}."
                ),
                metadata=self.metadata,
            ),
        )

    # ---------- data used by other collections ----------

    def calculate_demand(self, sector: str) -> pd.Series:
        """Product demand (t/h): production capacity at the plants' operating hours."""
        demand = self._capacity[sector].rename("demand")
        demand.index.name = "node"
        return demand

    def calculate_production(self, sector: str) -> pd.Series:
        """Physical production (t/h), averaged over the year."""
        return self._production[sector]

    def calculate_energy_intensity(self, sector: str) -> pd.Series:
        """Fuel (above 200 °C), heat and electricity demand (GW per t/h)."""
        parameters = self._sector_parameters.loc[sector]
        energy = pd.Series({
            "fuel": parameters["fuel"],
            "heat_0_100": parameters["heat_0_100"],
            "heat_100_200": parameters["heat_100_200"],
            "heat": parameters["heat_0_100"] + parameters["heat_100_200"],
            "electricity": parameters["electricity"],
        })
        return energy / Constants.SECONDS_PER_HOUR  # GJ/t -> GW/(t/h)

    def calculate_fuel_intensity(self, sector: str) -> pd.Series:
        """Fuel demand (GW per t/h) per fuel carrier, incl. the kiln fuel."""
        fuel = self.calculate_energy_intensity(sector)["fuel"]
        return (fuel * self._calculate_fuel_inputs(sector)).round(12)

    def calculate_heat_conversion_factors(self, sector: str) -> pd.Series:
        """Heat demand per band (GW per t/h), 100-200 °C split by Wolf (2017)."""
        energy = self.calculate_energy_intensity(sector)
        wolf = cast(Wolf2017, self.data["wolf2017"])
        split = wolf.get_temperature_split().loc[sector]
        return pd.Series({
            "0_100": energy["heat_0_100"],
            "100_150": energy["heat_100_200"] * split["100_150"],
            "150_200": energy["heat_100_200"] * split["150_200"],
        })

    def calculate_fuel_shares(self, sector: str) -> pd.Series:
        """Fuel mix of the sector's thermal energy (EU27), small fuels dropped."""
        idees = cast(JRCIDEESIndustry, self.data["jrc_idees_industry"])
        thermal = idees.get_thermal_final_energy(
            sector, self.settings.industry.data_year).loc[IDEES_EU]
        shares = thermal / thermal.sum()
        shares = shares[shares.index.isin(list(FUELS))]
        shares = shares[shares >= self.settings.industry.fuel_share_cutoff]
        shares = shares.rename(FUELS)
        return shares / shares.sum()

    # ---------- helpers ----------

    def _calculate_fuel_inputs(self, sector: str) -> pd.Series:
        """Fuel shares, with the switchable kiln natural gas as kiln fuel."""
        shares = self.calculate_fuel_shares(sector)
        if sector not in KILN_SWITCHABLE_SHARE or "natural_gas" not in shares:
            return shares
        switchable = KILN_SWITCHABLE_SHARE[sector]
        natural_gas = shares.pop("natural_gas")
        shares[f"fuel_to_kiln_{sector}"] = natural_gas * switchable
        if natural_gas * (1 - switchable) > 1e-12:
            shares["natural_gas"] = natural_gas * (1 - switchable)
        return shares

    def _active_heat_levels(self, element: Element) -> list[str]:
        heat = self.calculate_heat_conversion_factors(element.sector)
        return [level for level in HEAT_LEVELS if heat[level] > 0]

    @cached_property
    def _capacity(self) -> pd.DataFrame:
        """Production capacity (t/h) at the plants' operating hours, per node and
        sector."""
        hours = self.settings.industry.operating_hours
        year = self.settings.industry.data_year
        idees = cast(JRCIDEESIndustry, self.data["jrc_idees_industry"])
        capacity = pd.DataFrame({
            "glass": self._fill_proxy_nodes(
                self._reindex_nodes(idees.get_installed_capacity("glass", year))),
            "ceramic": self._ceramic_output,
            "paper": self._reindex_nodes(idees.get_installed_capacity("paper", year)),
        }) * 1000 / hours  # kt/a -> t/h
        capacity["food"] = self._food_capacity
        # paper: the consumption of the nodes without JRC-IDEES (JRC BAT)
        jrc_bat = cast(JRCBATPaper, self.data["jrc_bat_paper"])
        consumption = jrc_bat.get_consumption()
        capacity.loc[consumption.index, "paper"] = consumption * 1000 / hours
        return capacity

    @cached_property
    def _production(self) -> pd.DataFrame:
        """Physical production (t/h) averaged over the year, per node and sector."""
        year = self.settings.industry.data_year
        idees = cast(JRCIDEESIndustry, self.data["jrc_idees_industry"])
        production = pd.DataFrame({
            "glass": self._fill_proxy_nodes(
                self._reindex_nodes(idees.get_physical_output("glass", year))),
            "ceramic": self._ceramic_output,
            "paper": self._reindex_nodes(idees.get_physical_output("paper", year)),
        }) * 1000.0 / Constants.HOURS_PER_YEAR  # kt/a -> t/h
        production["food"] = self._food_capacity
        return production

    @cached_property
    def _ceramic_output(self) -> pd.Series:
        """Ceramic output (kt/a): JRC-IDEES thermal energy / Rehfeldt fuel intensity."""
        idees = cast(JRCIDEESIndustry, self.data["jrc_idees_industry"])
        thermal = idees.get_thermal_final_energy(
            "ceramic", self.settings.industry.data_year).sum(axis=1)  # ktoe
        intensity = self._sector_parameters.at["ceramic", "fuel_total"]  # GJ/t
        output = thermal * Constants.GJ_PER_KTOE / (intensity * 1000)
        return self._fill_proxy_nodes(self._reindex_nodes(output))

    @cached_property
    def _food_capacity(self) -> pd.Series:
        """Food capacity (t/h): Rehfeldt (2017) activity split by FAOSTAT production."""
        rehfeldt = cast(Rehfeldt2017, self.data["rehfeldt2017"])
        faostat = cast(FAOSTATFood, self.data["faostat_food"])
        activity = rehfeldt.get_sub_processes("food").loc[list(FOOD_ITEMS), "activity_Mt"]
        production = faostat.get_production(self.settings.industry.data_year)
        production = production.reindex(
            index=list(FOOD_ITEMS.values()),
            columns=self.settings.region.set_nodes,
            fill_value=0.0,
        )
        production.index = list(FOOD_ITEMS)
        shares = production.div(production.sum(axis=1), axis=0).fillna(0.0)
        activity = shares.mul(activity, axis=0).sum()  # Mt/a
        return activity * 1e6 / self.settings.industry.operating_hours  # Mt/a -> t/h

    def _reindex_nodes(self, data: pd.Series) -> pd.Series:
        """Select the model nodes; nodes without data are 0."""
        return data.reindex(self.settings.region.set_nodes, fill_value=0.0)

    def _fill_proxy_nodes(self, data: pd.Series) -> pd.Series:
        """Fill the nodes without JRC-IDEES data from their proxy node."""
        data = data.copy()
        for node, (proxy, factor) in PROXY_NODES.items():
            data[node] = data[proxy] * factor
        return data

    @cached_property
    def _sector_parameters(self) -> pd.DataFrame:
        """Energy intensity (GJ/t) per sector, heat split by temperature."""
        rehfeldt = cast(Rehfeldt2017, self.data["rehfeldt2017"])
        aidres = cast(AIDRESGlass, self.data["aidres_glass"])
        parameters = {}
        for sector in SECTORS:
            if sector == "glass":
                energy = aidres.get_sub_processes().rename(columns={"ng_GJ_t": "fuel"})
                weights = aidres.get_production_shares()
            else:
                energy = rehfeldt.get_sub_processes(sector).rename(
                    columns={"fuels_GJ_t": "fuel"})
                weights = rehfeldt.get_activity_weights(sector)
            temperatures = rehfeldt.get_sub_processes(sector)
            fuel = weights.dot(energy.loc[weights.index, "fuel"])
            share_0_100 = weights.dot(temperatures.loc[weights.index, "temp_lt100"])
            share_100_200 = weights.dot(temperatures.loc[weights.index, "temp_100_200"])
            parameters[sector] = {
                "fuel_total": fuel,
                "fuel": fuel * (1.0 - share_0_100 - share_100_200),
                "heat_0_100": fuel * share_0_100,
                "heat_100_200": fuel * share_100_200,
                "electricity": weights.dot(energy.loc[weights.index, "elec_GJ_t"]),
            }
        return pd.DataFrame.from_dict(parameters, orient="index")

    @cached_property
    def _costs(self) -> pd.DataFrame:
        """Lifetime and costs per sector, see docs, "Production technologies"."""
        aidres = cast(AIDRESGlass, self.data["aidres_glass"])
        rehfeldt = cast(Rehfeldt2017, self.data["rehfeldt2017"])
        ecb = cast(ECBInflation, self.data["ecb"])
        reference_year = self.settings.time.reference_year
        hours = Constants.HOURS_PER_YEAR
        costs = {
            "glass": self._calculate_jrc_costs("glass", aidres.get_production_shares()),
            "paper": self._calculate_jrc_costs(
                "paper", rehfeldt.get_activity_weights("paper")),
        }
        costs["paper"]["capex"] = round(PAPER_CAPEX * hours, 2)  # Euro/(t/a) -> Euro/(t/h)
        inflation = ecb.get_inflation_rate(BASE_YEAR, reference_year)
        costs["food"] = {
            "capex": round(FOOD_COSTS["capex"] * inflation * hours, 2),
            "opex_fixed": round(FOOD_COSTS["opex_fixed"] * inflation * hours, 2),
            "opex_variable": 0.0,
            "lifetime": 20,
        }
        # fixed opex: maintenance 2.5 %, insurance 2 %, labour 100 x 60 kEUR, overhead
        inflation = ecb.get_inflation_rate(CERAMIC_PLANT["price_year"], reference_year)
        capacity = CERAMIC_PLANT["capacity_t_h"]
        investment = CERAMIC_PLANT["investment"]
        opex_fixed = (
            0.025 * investment
            + 0.02 * investment
            + 100 * 60e3
            + 0.30 * (100 * 60e3 + 0.40 * 0.025 * investment)
        )
        # raw meal, NOx reagent and other variable O&M, without energy (Euro/t)
        opex_variable = 5.0 + 0.65 + 1.1
        costs["ceramic"] = {
            "capex": round(investment / capacity * inflation, 2),
            "opex_fixed": round(opex_fixed / capacity * inflation, 2),
            "opex_variable": round(opex_variable * inflation, 2),
            "lifetime": 25,
        }
        return pd.DataFrame.from_dict(costs, orient="index")

    def _calculate_jrc_costs(self, sector: str, weights: pd.Series) -> dict[str, float]:
        """Weighted JRC-EU-TIMES costs of the sector's processes."""
        times = cast(JRCEUTIMESIndustry, self.data["jrc_eu_times_industry"])
        ecb = cast(ECBInflation, self.data["ecb"])
        inflation = ecb.get_inflation_rate(BASE_YEAR, self.settings.time.reference_year)
        parameters = pd.DataFrame({
            sub_process: times.get_process_parameters(process)
            for sub_process, process in JRC_PROCESSES[sector].items()
        })
        weighted = parameters.dot(weights[parameters.columns])
        hours = Constants.HOURS_PER_YEAR
        return {
            # Euro/(t/a) -> Euro/(t/h)
            "capex": weighted["INVCOST"] * inflation * hours,
            "opex_fixed": weighted["FIXOM"] * inflation * hours,
            "opex_variable": weighted["VAROM"] * inflation,
            "lifetime": round(weighted["LIFE"]),
        }

    def _cost_source(self, sector: str) -> SourceInformation:
        descriptions = {
            "glass": (
                "JRC-EU-TIMES costs and lifetime of the glass processes, weighted by "
                "the AIDRES (2023) EU production shares of the glass routes."
            ),
            "paper": (
                "JRC-EU-TIMES costs and lifetime of the paper processes, weighted by "
                "the Rehfeldt et al. (2017) activity; capex of "
                f"{PAPER_CAPEX} Euro/(t/a) from the literature (not inflated)."
            ),
            "food": (
                f"Capex of {FOOD_COSTS['capex']} Euro/(t/a) and fixed opex of "
                f"{FOOD_COSTS['opex_fixed']} Euro/(t/a) from the literature, "
                "lifetime of 20 years."
            ),
            "ceramic": (
                "Costs of the Gardarsdottir et al. (2019) reference cement plant as a "
                "proxy, lifetime of 25 years."
            ),
        }
        return SourceInformation(
            description=(
                f"{descriptions[sector]} Costs in "
                f"{self.settings.time.reference_year} Euro using ECB HICP inflation, "
                "see docs, 'Production technologies'."
            ),
            metadata=self.metadata,
        )
