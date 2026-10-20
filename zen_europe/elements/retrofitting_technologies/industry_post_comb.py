from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from zen_creator import RetrofittingTechnology
from zen_creator.datasets.datasets.metadata import AssumptionInformation
from zen_creator.utils.attribute import Attribute

from zen_europe.datasets.dataset_collections.industry_production_data import (
    IndustryProductionData,
)
from zen_europe.datasets.dataset_collections.technology_cost_database import (
    TechnologyCostDatabase,
)
from zen_europe.datasets.datasets.technology.technology_diffusion_mannhardt import (
    TechnologyDiffusionMannhardt,
)

if TYPE_CHECKING:
    from zen_creator.model import Model

# costs and diffusion of the same DEA capture unit as the cement kiln
COST_PROXY = "cement_post_comb"


class IndustryPostComb:
    """Post-combustion capture of a kiln's process CO2, as cement_post_comb."""

    sector: ClassVar[str]

    def __init__(self, model: Model, power_unit: str = "tCO2/h"):
        super().__init__(model=model, power_unit=power_unit)

    # ---------- Required methods that are called during object construction ----------

    def _set_reference_carrier(self) -> Attribute:
        """Captured carbon."""
        return Attribute("reference_carrier", default_value=["carbon"], element=self)

    def _set_input_carrier(self) -> Attribute:
        """Heat from natural gas and coal, electricity."""
        return Attribute(
            "input_carrier",
            default_value=["natural_gas", "hard_coal", "electricity"],
            element=self,
        )

    def _set_output_carrier(self) -> Attribute:
        """Captured carbon and waste heat."""
        return Attribute(
            "output_carrier", default_value=["carbon", "district_heat"], element=self
        )

    def _set_retrofit_reference_carrier(self) -> Attribute:
        """Captured carbon."""
        return Attribute(
            "retrofit_reference_carrier", default_value=["carbon"], element=self
        )

    # ---------- Required methods that are called during object build ----------

    def _set_conversion_factor(self) -> Attribute:
        """Capture unit from DEA, heat from the sector's fuels."""
        return self._data().get_conversion_factor_post_comb(self)

    def _set_retrofit_flow_coupling_factor(self) -> Attribute:
        """Process emissions times the capture rate."""
        return self._data().get_retrofit_flow_coupling_factor(self)

    def _set_lifetime(self) -> Attribute:
        """Lifetime from DEA."""
        return self._cost_db().get_lifetime(self, proxy_element_name=COST_PROXY)

    def _set_capex_specific_conversion(self) -> Attribute:
        """Investment cost from DEA."""
        return self._cost_db().get_capex_specific_conversion(
            self, proxy_element_name=COST_PROXY
        )

    def _set_opex_specific_fixed(self) -> Attribute:
        """Fixed O&M cost from DEA."""
        return self._cost_db().get_opex_specific_fixed(
            self, proxy_element_name=COST_PROXY
        )

    def _set_opex_specific_variable(self) -> Attribute:
        """Variable O&M cost from DEA."""
        return self._cost_db().get_opex_specific_variable(
            self, proxy_element_name=COST_PROXY
        )

    def _set_carbon_intensity_technology(self) -> Attribute:
        """No own emissions."""
        return self.carbon_intensity_technology.set_data(
            default_value=0.0,
            unit="ton/tCO2",
            source=AssumptionInformation(description="No own emissions."),
        )

    def _set_capacity_addition_unbounded(self) -> Attribute:
        """As cement_post_comb."""
        cement = self.model.elements["cement_post_comb"].capacity_addition_unbounded
        return self.capacity_addition_unbounded.set_data(
            default_value=cement.default_value,
            unit=cement.unit,
            source=AssumptionInformation(description="As cement_post_comb."),
        )

    def _set_max_diffusion_rate(self) -> Attribute:
        """As cement_post_comb."""
        if not self.settings.investment.use_diffusion_rates:
            return self.max_diffusion_rate
        diffusion_rates = TechnologyDiffusionMannhardt(source_path=self.source_path)
        return diffusion_rates.get_max_diffusion_rate(
            self, proxy_element_name=COST_PROXY
        )

    def _data(self) -> IndustryProductionData:
        return IndustryProductionData(self.settings, self.source_path)

    def _cost_db(self) -> TechnologyCostDatabase:
        return TechnologyCostDatabase(self.settings, self.source_path)


class GlassPostComb(IndustryPostComb, RetrofittingTechnology):
    name: str = "glass_post_comb"
    sector: ClassVar[str] = "glass"


class CeramicPostComb(IndustryPostComb, RetrofittingTechnology):
    name: str = "ceramic_post_comb"
    sector: ClassVar[str] = "ceramic"
