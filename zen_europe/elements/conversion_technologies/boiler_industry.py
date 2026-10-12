from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from zen_creator import ConversionTechnology
from zen_creator.datasets.datasets.metadata import (
    AssumptionInformation,
    SourceInformation,
)
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


class BoilerIndustry:
    """
    Industrial boiler of one sector, supplying the 150-200 °C band.

    The boilers exist for every combination of fuel and sector. The shared data and
    assumptions are defined once in this mixin and the fuel mixins below; the
    concrete technologies at the end of the module only set the sector.
    """

    sector: ClassVar[str]
    fuel: ClassVar[str]
    input: ClassVar[str]
    # DEA technology the costs, lifetime and efficiency are taken from
    cost_proxy: ClassVar[str]

    def __init__(self, model: Model, power_unit: str = "GW"):
        super().__init__(model=model, power_unit=power_unit)

    # ---------- Required methods that are called during object construction ----------

    def _set_reference_carrier(self) -> Attribute:
        """Heat of the sector's 150-200 °C band."""
        return Attribute(
            "reference_carrier", default_value=[self._heat()], element=self
        )

    def _set_input_carrier(self) -> Attribute:
        """Fuel of the boiler."""
        return Attribute("input_carrier", default_value=[self.input], element=self)

    def _set_output_carrier(self) -> Attribute:
        """Heat of the sector's 150-200 °C band."""
        return Attribute("output_carrier", default_value=[self._heat()], element=self)

    # ---------- Required methods that are called during object build ----------

    def _set_conversion_factor(self) -> Attribute:
        """Inverse of the DEA efficiency."""
        tech_db = self._cost_db()
        efficiency, agencies = tech_db.get_efficiency(
            self, proxy_element_name=self.cost_proxy
        )
        efficiency = efficiency.loc[self.settings.time.reference_year]
        return self.conversion_factor.set_data(
            default_value=[
                {self.input: {"default_value": 1 / efficiency, "unit": "GW/GW"}}
            ],
            source=SourceInformation(
                description=(
                    f"Inverse of the efficiency of '{self.cost_proxy}' "
                    f"from {', '.join(agencies)}."
                ),
                metadata=tech_db.metadata,
            ),
        )

    def _set_lifetime(self) -> Attribute:
        """Lifetime from DEA."""
        return self._cost_db().get_lifetime(self, proxy_element_name=self.cost_proxy)

    def _set_capex_specific_conversion(self) -> Attribute:
        """Investment cost from DEA."""
        return self._cost_db().get_capex_specific_conversion(
            self, proxy_element_name=self.cost_proxy
        )

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

    def _set_construction_time(self) -> Attribute:
        """Construction time from DEA."""
        if not self.settings.investment.use_construction_times:
            return self.construction_time
        return self._cost_db().get_construction_time(
            self, proxy_element_name=self.cost_proxy
        )

    def _set_capacity_existing(self) -> Attribute:
        """Today's heat demand, split by fuel."""
        if not self.settings.investment.use_existing_capacities:
            return self.capacity_existing.set_data(
                default_value=0,
                df=None,
                source=AssumptionInformation(
                    description="We do not consider existing capacities."
                ),
            )
        return IndustryHeatSupply(
            self.settings, self.source_path
        ).get_capacity_existing_boiler(self)

    def _set_max_diffusion_rate(self) -> Attribute:
        """Max diffusion rate, as the district heating boilers."""
        if not self.settings.investment.use_diffusion_rates:
            return self.max_diffusion_rate
        diffusion_rates = TechnologyDiffusionMannhardt(source_path=self.source_path)
        return diffusion_rates.get_max_diffusion_rate(self)

    def _heat(self) -> str:
        return f"heat_industry_150_200_{self.sector}"

    def _cost_db(self) -> TechnologyCostDatabase:
        return TechnologyCostDatabase(self.settings, self.source_path)


class BiomassBoilerIndustry(BoilerIndustry):
    fuel: ClassVar[str] = "biomass"
    input: ClassVar[str] = "biomass"
    cost_proxy: ClassVar[str] = "biomass_boiler_industry"


class ElectrodeBoilerIndustry(BoilerIndustry):
    fuel: ClassVar[str] = "electrode"
    input: ClassVar[str] = "electricity"
    cost_proxy: ClassVar[str] = "electrode_boiler_industry"


class NaturalGasBoilerIndustry(BoilerIndustry):
    fuel: ClassVar[str] = "natural_gas"
    input: ClassVar[str] = "natural_gas"
    cost_proxy: ClassVar[str] = "natural_gas_boiler_industry"


class OilBoilerIndustry(BoilerIndustry):
    fuel: ClassVar[str] = "oil"
    input: ClassVar[str] = "oil"
    cost_proxy: ClassVar[str] = "oil_boiler_industry"


class CoalBoilerIndustry(BoilerIndustry):
    fuel: ClassVar[str] = "coal"
    input: ClassVar[str] = "hard_coal"
    cost_proxy: ClassVar[str] = "coal_boiler_industry"


class WasteBoilerIndustry(BoilerIndustry):
    """No DEA data: efficiency, lifetime and costs as the DH waste boiler."""

    fuel: ClassVar[str] = "waste"
    input: ClassVar[str] = "waste"

    def _set_conversion_factor(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.conversion_factor.set_data(
            default_value=dh_boiler.conversion_factor.default_value,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )

    def _set_lifetime(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.lifetime.set_data(
            default_value=dh_boiler.lifetime.default_value,
            unit=dh_boiler.lifetime.unit,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )

    def _set_construction_time(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.construction_time.set_data(
            default_value=dh_boiler.construction_time.default_value,
            unit=dh_boiler.construction_time.unit,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )

    def _set_capex_specific_conversion(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.capex_specific_conversion.set_data(
            default_value=dh_boiler.capex_specific_conversion.default_value,
            unit=dh_boiler.capex_specific_conversion.unit,
            df=dh_boiler.capex_specific_conversion.df,
            yearly_variations_df=dh_boiler.capex_specific_conversion.yearly_variations_df,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )

    def _set_opex_specific_fixed(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.opex_specific_fixed.set_data(
            default_value=dh_boiler.opex_specific_fixed.default_value,
            unit=dh_boiler.opex_specific_fixed.unit,
            df=dh_boiler.opex_specific_fixed.df,
            yearly_variations_df=dh_boiler.opex_specific_fixed.yearly_variations_df,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )

    def _set_opex_specific_variable(self) -> Attribute:
        """As waste_boiler_DH."""
        dh_boiler = self.model.conversion_technologies["waste_boiler_DH"]
        return self.opex_specific_variable.set_data(
            default_value=dh_boiler.opex_specific_variable.default_value,
            unit=dh_boiler.opex_specific_variable.unit,
            df=dh_boiler.opex_specific_variable.df,
            yearly_variations_df=dh_boiler.opex_specific_variable.yearly_variations_df,
            source=AssumptionInformation(description="As waste_boiler_DH."),
        )


class BiomassBoilerIndustryGlass(BiomassBoilerIndustry, ConversionTechnology):
    name: str = "biomass_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class BiomassBoilerIndustryCeramic(BiomassBoilerIndustry, ConversionTechnology):
    name: str = "biomass_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class BiomassBoilerIndustryPaper(BiomassBoilerIndustry, ConversionTechnology):
    name: str = "biomass_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class BiomassBoilerIndustryFood(BiomassBoilerIndustry, ConversionTechnology):
    name: str = "biomass_boiler_industry_food"
    sector: ClassVar[str] = "food"


class ElectrodeBoilerIndustryGlass(ElectrodeBoilerIndustry, ConversionTechnology):
    name: str = "electrode_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class ElectrodeBoilerIndustryCeramic(ElectrodeBoilerIndustry, ConversionTechnology):
    name: str = "electrode_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class ElectrodeBoilerIndustryPaper(ElectrodeBoilerIndustry, ConversionTechnology):
    name: str = "electrode_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class ElectrodeBoilerIndustryFood(ElectrodeBoilerIndustry, ConversionTechnology):
    name: str = "electrode_boiler_industry_food"
    sector: ClassVar[str] = "food"


class NaturalGasBoilerIndustryGlass(NaturalGasBoilerIndustry, ConversionTechnology):
    name: str = "natural_gas_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class NaturalGasBoilerIndustryCeramic(NaturalGasBoilerIndustry, ConversionTechnology):
    name: str = "natural_gas_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class NaturalGasBoilerIndustryPaper(NaturalGasBoilerIndustry, ConversionTechnology):
    name: str = "natural_gas_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class NaturalGasBoilerIndustryFood(NaturalGasBoilerIndustry, ConversionTechnology):
    name: str = "natural_gas_boiler_industry_food"
    sector: ClassVar[str] = "food"


class OilBoilerIndustryGlass(OilBoilerIndustry, ConversionTechnology):
    name: str = "oil_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class OilBoilerIndustryCeramic(OilBoilerIndustry, ConversionTechnology):
    name: str = "oil_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class OilBoilerIndustryPaper(OilBoilerIndustry, ConversionTechnology):
    name: str = "oil_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class OilBoilerIndustryFood(OilBoilerIndustry, ConversionTechnology):
    name: str = "oil_boiler_industry_food"
    sector: ClassVar[str] = "food"


class CoalBoilerIndustryGlass(CoalBoilerIndustry, ConversionTechnology):
    name: str = "coal_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class CoalBoilerIndustryCeramic(CoalBoilerIndustry, ConversionTechnology):
    name: str = "coal_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class CoalBoilerIndustryPaper(CoalBoilerIndustry, ConversionTechnology):
    name: str = "coal_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class CoalBoilerIndustryFood(CoalBoilerIndustry, ConversionTechnology):
    name: str = "coal_boiler_industry_food"
    sector: ClassVar[str] = "food"


class WasteBoilerIndustryGlass(WasteBoilerIndustry, ConversionTechnology):
    name: str = "waste_boiler_industry_glass"
    sector: ClassVar[str] = "glass"


class WasteBoilerIndustryCeramic(WasteBoilerIndustry, ConversionTechnology):
    name: str = "waste_boiler_industry_ceramic"
    sector: ClassVar[str] = "ceramic"


class WasteBoilerIndustryPaper(WasteBoilerIndustry, ConversionTechnology):
    name: str = "waste_boiler_industry_paper"
    sector: ClassVar[str] = "paper"


class WasteBoilerIndustryFood(WasteBoilerIndustry, ConversionTechnology):
    name: str = "waste_boiler_industry_food"
    sector: ClassVar[str] = "food"
