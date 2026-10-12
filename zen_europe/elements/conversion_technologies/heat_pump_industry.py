from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from zen_creator import ConversionTechnology
from zen_creator.datasets.datasets.metadata import AssumptionInformation
from zen_creator.utils.attribute import Attribute

from zen_europe.datasets.dataset_collections.industry_heat_supply import (
    IndustryHeatSupply,
)
from zen_europe.datasets.dataset_collections.technology_cost_database import (
    TechnologyCostDatabase,
)
from zen_europe.datasets.datasets.technology.technology_diffusion_mannhardt import (
    TechnologyDiffusionMannhardt,
)

if TYPE_CHECKING:
    from zen_creator.model import Model


class HeatPumpIndustry:
    """
    Industrial heat pump of a sector and temperature band, on waste heat or water.

    The heat pumps exist for every combination of band, heat source and sector. The
    shared data and assumptions are defined once in this mixin; the concrete
    technologies at the end of the module only set the combination.
    """

    sector: ClassVar[str]
    temp_level: ClassVar[str]
    heat_source: ClassVar[str]

    def __init__(self, model: Model, power_unit: str = "GW"):
        super().__init__(model=model, power_unit=power_unit)

    @property
    def cost_proxy(self) -> str:
        """DEA heat pumps up to 125 °C and 150 °C; the latter also for 150-200 °C."""
        if self.temp_level == "0_100":
            return "heat_pump_industry_125"
        return "heat_pump_industry_150"

    # ---------- Required methods that are called during object construction ----------

    def _set_reference_carrier(self) -> Attribute:
        """Heat of the sector's temperature band."""
        return Attribute(
            "reference_carrier", default_value=[self._heat()], element=self
        )

    def _set_input_carrier(self) -> Attribute:
        """Electricity."""
        return Attribute("input_carrier", default_value=["electricity"], element=self)

    def _set_output_carrier(self) -> Attribute:
        """Heat of the sector's temperature band."""
        return Attribute("output_carrier", default_value=[self._heat()], element=self)

    # ---------- Required methods that are called during object build ----------

    def _set_conversion_factor(self) -> Attribute:
        """Half the Carnot COP."""
        return self._supply().get_conversion_factor_heat_pump(self)

    def _set_lifetime(self) -> Attribute:
        """Lifetime from DEA."""
        return self._cost_db().get_lifetime(self, proxy_element_name=self.cost_proxy)

    def _set_capex_specific_conversion(self) -> Attribute:
        """Investment cost from DEA, plus waste-heat recovery."""
        return self._supply().get_capex_specific_conversion_heat_pump(self)

    def _set_opex_specific_fixed(self) -> Attribute:
        """Fixed O&M cost from DEA."""
        return self._cost_db().get_opex_specific_fixed(
            self, proxy_element_name=self.cost_proxy
        )

    def _set_opex_specific_variable(self) -> Attribute:
        """Variable O&M cost from DEA."""
        return self._cost_db().get_opex_specific_variable(
            self, proxy_element_name=self.cost_proxy
        )

    def _set_capacity_existing(self) -> Attribute:
        """No industrial heat pumps today."""
        return self.capacity_existing.set_data(
            default_value=0.0,
            unit="GW",
            source=AssumptionInformation(
                description="No existing industrial heat pumps."
            ),
        )

    def _set_capacity_limit(self) -> Attribute:
        """Waste heat available in the sector; unlimited for water."""
        if self.heat_source == "water":
            return self.capacity_limit
        return self._supply().get_capacity_limit_heat_pump(self)

    def _set_capacity_addition_unbounded(self) -> Attribute:
        """Seed from the district heating heat pumps."""
        return self._supply().get_capacity_addition_unbounded_heat_pump(self)

    def _set_construction_time(self) -> Attribute:
        """Construction time from DEA."""
        if not self.settings.investment.use_construction_times:
            return self.construction_time
        return self._cost_db().get_construction_time(
            self, proxy_element_name=self.cost_proxy
        )

    def _set_max_diffusion_rate(self) -> Attribute:
        """Max diffusion rate, as the district heating heat pumps."""
        if not self.settings.investment.use_diffusion_rates:
            return self.max_diffusion_rate
        diffusion_rates = TechnologyDiffusionMannhardt(source_path=self.source_path)
        return diffusion_rates.get_max_diffusion_rate(self)

    def _heat(self) -> str:
        return f"heat_industry_{self.temp_level}_{self.sector}"

    def _supply(self) -> IndustryHeatSupply:
        return IndustryHeatSupply(self.settings, self.source_path)

    def _cost_db(self) -> TechnologyCostDatabase:
        return TechnologyCostDatabase(self.settings, self.source_path)


class HeatPumpIndustry0100WasteHeatGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_waste_heat_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry0100WasteHeatCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_waste_heat_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry0100WasteHeatPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_waste_heat_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry0100WasteHeatFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_waste_heat_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry0100WaterGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_water_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry0100WaterCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_water_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry0100WaterPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_water_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry0100WaterFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_0_100_water_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "0_100"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry100150WasteHeatGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_waste_heat_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry100150WasteHeatCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_waste_heat_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry100150WasteHeatPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_waste_heat_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry100150WasteHeatFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_waste_heat_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry100150WaterGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_water_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry100150WaterCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_water_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry100150WaterPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_water_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry100150WaterFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_100_150_water_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "100_150"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry150200WasteHeatGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_waste_heat_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry150200WasteHeatCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_waste_heat_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry150200WasteHeatPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_waste_heat_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry150200WasteHeatFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_waste_heat_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "waste_heat"


class HeatPumpIndustry150200WaterGlass(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_water_glass"
    sector: ClassVar[str] = "glass"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry150200WaterCeramic(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_water_ceramic"
    sector: ClassVar[str] = "ceramic"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry150200WaterPaper(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_water_paper"
    sector: ClassVar[str] = "paper"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "water"


class HeatPumpIndustry150200WaterFood(HeatPumpIndustry, ConversionTechnology):
    name: str = "heat_pump_industry_150_200_water_food"
    sector: ClassVar[str] = "food"
    temp_level: ClassVar[str] = "150_200"
    heat_source: ClassVar[str] = "water"
