from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from zen_creator import StorageTechnology
from zen_creator.datasets.datasets.metadata import AssumptionInformation
from zen_creator.utils.attribute import Attribute

from zen_europe.datasets.dataset_collections.industry_heat_supply import (
    IndustryHeatSupply,
)
from zen_europe.datasets.datasets.technology.brown2018 import Brown2018
from zen_europe.datasets.datasets.technology.mayer2024 import Mayer2024
from zen_europe.utils.industry import heat_carrier

if TYPE_CHECKING:
    from zen_creator.model import Model

# (dis)charging losses neglected, own assumption
TES_EFFICIENCY = 1.0
# variable O&M (Euro/GWh) against spurious cycling, own assumption
TES_OPEX_VARIABLE = 1.0


class IndustryTES:
    """Thermal energy storage for one sector and temperature band."""

    sector: ClassVar[str]
    temp_level: ClassVar[str]
    storage_type: ClassVar[str]
    # energy-to-power ratio (h): water tanks are intraday buffers of at least 1 h,
    # steam accumulators are short-duration pressure vessels
    duration: ClassVar[tuple[float, float]]
    # Brown et al. (2018) technology for the self-discharge
    self_discharge_proxy: ClassVar[str] = "hot water tank decentral"

    def __init__(self, model: Model, power_unit: str = "MW"):
        super().__init__(model=model, power_unit=power_unit)

    # ---------- Required methods that are called during object construction ----------

    def _set_reference_carrier(self) -> Attribute:
        """Heat of the sector's temperature band."""
        return Attribute(
            "reference_carrier",
            default_value=[heat_carrier(self.temp_level, self.sector)],
            element=self,
        )

    # ---------- Required methods that are called during object build ----------

    def _set_lifetime(self) -> Attribute:
        """Lifetime from Mayer et al. (2024)."""
        return Mayer2024(self.source_path).get_lifetime(self)

    def _set_capex_specific_storage_energy(self) -> Attribute:
        """Investment cost from Mayer et al. (2024)."""
        return Mayer2024(self.source_path).get_capex_specific_storage_energy(self)

    def _set_opex_specific_fixed_energy(self) -> Attribute:
        """Fixed O&M cost from Mayer et al. (2024)."""
        return Mayer2024(self.source_path).get_opex_specific_fixed_energy(self)

    def _set_efficiency_charge(self) -> Attribute:
        """Losses neglected."""
        return self.efficiency_charge.set_data(
            default_value=TES_EFFICIENCY,
            unit="1",
            source=AssumptionInformation(description="Losses neglected."),
        )

    def _set_efficiency_discharge(self) -> Attribute:
        """Losses neglected."""
        return self.efficiency_discharge.set_data(
            default_value=TES_EFFICIENCY,
            unit="1",
            source=AssumptionInformation(description="Losses neglected."),
        )

    def _set_self_discharge(self) -> Attribute:
        """Self-discharge from Brown et al. (2018)."""
        return Brown2018(self.source_path).get_self_discharge(
            self, self.self_discharge_proxy
        )

    def _set_opex_specific_variable(self) -> Attribute:
        """Small cost against cycling."""
        return self.opex_specific_variable.set_data(
            default_value=TES_OPEX_VARIABLE,
            unit="Euro/GWh",
            source=AssumptionInformation(description="Against cycling."),
        )

    def _set_capacity_limit(self) -> Attribute:
        """Heat demand of the band and all lower bands times the capacity limit
        margin."""
        return IndustryHeatSupply(
            self.settings, self.source_path
        ).get_capacity_limit_tes(self)

    def _set_energy_to_power_ratio_min(self) -> Attribute:
        """Minimum duration of the storage type."""
        return self.energy_to_power_ratio_min.set_data(
            default_value=self.duration[0],
            unit="h",
            source=AssumptionInformation(
                description=f"Minimum duration of a {self.storage_type}."
            ),
        )

    def _set_energy_to_power_ratio_max(self) -> Attribute:
        """Maximum duration of the storage type."""
        return self.energy_to_power_ratio_max.set_data(
            default_value=self.duration[1],
            unit="h",
            source=AssumptionInformation(
                description=f"Maximum duration of a {self.storage_type}."
            ),
        )


class IndustryTESWater0100(IndustryTES):
    temp_level: ClassVar[str] = "0_100"
    storage_type: ClassVar[str] = "water tank"
    duration: ClassVar[tuple[float, float]] = (1.0, 24.0)


class IndustryTESWater100150(IndustryTES):
    temp_level: ClassVar[str] = "100_150"
    storage_type: ClassVar[str] = "water tank"
    duration: ClassVar[tuple[float, float]] = (1.0, 24.0)


class IndustryTESSteam150200(IndustryTES):
    temp_level: ClassVar[str] = "150_200"
    storage_type: ClassVar[str] = "steam accumulator"
    duration: ClassVar[tuple[float, float]] = (0.25, 4.0)


class IndustryTESWater0100Glass(IndustryTESWater0100, StorageTechnology):
    name: str = "industry_TES_water_0_100_glass"
    sector: ClassVar[str] = "glass"


class IndustryTESWater0100Ceramic(IndustryTESWater0100, StorageTechnology):
    name: str = "industry_TES_water_0_100_ceramic"
    sector: ClassVar[str] = "ceramic"


class IndustryTESWater0100Paper(IndustryTESWater0100, StorageTechnology):
    name: str = "industry_TES_water_0_100_paper"
    sector: ClassVar[str] = "paper"


class IndustryTESWater0100Food(IndustryTESWater0100, StorageTechnology):
    name: str = "industry_TES_water_0_100_food"
    sector: ClassVar[str] = "food"


class IndustryTESWater100150Glass(IndustryTESWater100150, StorageTechnology):
    name: str = "industry_TES_water_100_150_glass"
    sector: ClassVar[str] = "glass"


class IndustryTESWater100150Ceramic(IndustryTESWater100150, StorageTechnology):
    name: str = "industry_TES_water_100_150_ceramic"
    sector: ClassVar[str] = "ceramic"


class IndustryTESWater100150Paper(IndustryTESWater100150, StorageTechnology):
    name: str = "industry_TES_water_100_150_paper"
    sector: ClassVar[str] = "paper"


class IndustryTESWater100150Food(IndustryTESWater100150, StorageTechnology):
    name: str = "industry_TES_water_100_150_food"
    sector: ClassVar[str] = "food"


class IndustryTESSteam150200Glass(IndustryTESSteam150200, StorageTechnology):
    name: str = "industry_TES_steam_150_200_glass"
    sector: ClassVar[str] = "glass"


class IndustryTESSteam150200Ceramic(IndustryTESSteam150200, StorageTechnology):
    name: str = "industry_TES_steam_150_200_ceramic"
    sector: ClassVar[str] = "ceramic"


class IndustryTESSteam150200Paper(IndustryTESSteam150200, StorageTechnology):
    name: str = "industry_TES_steam_150_200_paper"
    sector: ClassVar[str] = "paper"


class IndustryTESSteam150200Food(IndustryTESSteam150200, StorageTechnology):
    name: str = "industry_TES_steam_150_200_food"
    sector: ClassVar[str] = "food"
