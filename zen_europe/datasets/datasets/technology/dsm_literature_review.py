from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.datasets.datasets.metadata import AssumptionInformation, MetaData
from zen_creator.utils.attribute import Attribute

from zen_europe.utils.constants import Constants

if TYPE_CHECKING:
    from zen_europe.elements.storage_technologies.industry_DSM import IndustryDSM

# demand-shiftability category per carrier, see docs, "Demand-side management"
CATEGORIES = {
    "glass": {"pessimistic": 1, "optimistic": 1},
    "ceramic": {"pessimistic": 1, "optimistic": 2},
    "paper": {"pessimistic": 2, "optimistic": 3},
    "food": {"pessimistic": 1, "optimistic": 2},
    "methanol": {"pessimistic": 2, "optimistic": 3},
    "primary_steel": {"pessimistic": 1, "optimistic": 1},
    "secondary_steel": {"pessimistic": 2, "optimistic": 3},
    "olefin": {"pessimistic": 1, "optimistic": 2},
    "ammonia": {"pessimistic": 1, "optimistic": 2},
    "clinker": {"pessimistic": 1, "optimistic": 1},
}
# reason and literature of the category of each carrier, see docs, "Demand-side
# management"
GOLMOHAMADI = "Golmohamadi (2021), doi:10.1016/j.rser.2021.111963"
BOLDRINI = "Boldrini et al. (2024), doi:10.1016/j.rser.2023.113988"
REFERENCES = {
    "glass": (
        "continuous furnace campaigns of 5-15 years; Hubert (2015), Basics of "
        "industrial glass melting furnaces, https://www.lehigh.edu/imi/teched/"
        "GlassProcess/Lectures/Lecture03_Hubert_industglassmeltfurnaces.pdf; Hongtai "
        "(2024), https://www.refractory-firebricks.com/case/343.html"
    ),
    "ceramic": (
        "tunnel kilns run continuously, batch kilns can stop between cycles; Tangram "
        "Technology, Energy management in ceramics processing, https://tangram.co.uk/"
        "wp-content/uploads/Energy-and-Sustainability-Topics-Energy-management-in-"
        "ceramics-processing.pdf"
    ),
    "paper": (
        "mechanical pulping with pulp storage; Helin et al. (2017), "
        "doi:10.1016/j.energy.2017.11.075"
    ),
    "food": "industry interview (TODO: reference)",
    "methanol": (
        "power-to-methanol can ramp; Schneider and Lagoni (2023), https://projekter."
        "aau.dk/projekter/files/535029626/Flexibility_of_Power_to_Methanol_in_2030.pdf"
        "; Chen and Yang (2021), doi:10.1016/j.enconman.2020.113673"
    ),
    "primary_steel": f"blast furnaces barely vary; {BOLDRINI}; {GOLMOHAMADI}",
    "secondary_steel": (
        f"electric arc furnace load flexibility; {BOLDRINI}; {GOLMOHAMADI}"
    ),
    "olefin": (
        "electrified crackers allow part load; Tiggeloven et al. (2023), "
        "doi:10.1021/acs.iecr.3c02226"
    ),
    "ammonia": (
        "flexible Haber-Bosch designs reach 10 % turndown; Salmon and "
        "Banares-Alcantara (2023), doi:10.1039/D3SU00067B; Fahr et al. (2025), "
        "doi:10.1016/j.ijhydene.2025.01.039"
    ),
    "clinker": f"uninterruptible; {GOLMOHAMADI}, Table 5",
}
# storage cost (Euro/tproduct), opex (Euro/tproduct) and horizon (h) per category:
# 1 = not flexible (priced out), 2 = partially flexible, 3 = fully flexible
CATEGORY_PARAMETERS = {
    1: {"capex": 1000.0, "opex": 1000.0, "energy_to_power_ratio_max": 2.0},
    2: {"capex": 20.0, "opex": 20.0, "energy_to_power_ratio_max": 48.0},
    3: {"capex": 1.0, "opex": 1.0, "energy_to_power_ratio_max": 336.0},
}
# energy content (GWh/t) of the carriers modeled on an energy basis
ENERGY_CONTENT = {
    "ammonia": Constants.AMMONIA_GWH_PER_TON,
    "methanol": Constants.METHANOL_KWH_PER_KG / 1000,  # kWh/kg -> GWh/t
}


class DSMLiteratureReview(Dataset[pd.DataFrame]):
    """Demand-shiftability category of industrial products from the literature."""

    name = "dsm_literature_review"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            title="Demand-shiftability of industrial products, literature review",
            author=["Goericke, H."],
            publication="docs/files/user_guide/industry.md",
            publication_year=2026,
            note=(
                "Based on Golmohamadi (2021), doi:10.1016/j.rser.2021.111963, and "
                "Boldrini et al. (2024), doi:10.1016/j.rser.2023.113988."
            ),
        )

    def _set_path(self) -> None:
        return None

    def _set_data(self) -> pd.DataFrame:
        return pd.DataFrame(CATEGORIES).T

    def get_capex_specific_storage_energy(self, element: IndustryDSM) -> Attribute:
        """Storage cost of the carrier's category."""
        return element.capex_specific_storage_energy.set_data(
            default_value=self._get_cost(element, "capex"),
            unit=f"Euro/({element.power_unit}*h)",
            source=self._source(element),
        )

    def get_opex_specific_variable(self, element: IndustryDSM) -> Attribute:
        """Variable cost of the carrier's category."""
        return element.opex_specific_variable.set_data(
            default_value=self._get_cost(element, "opex"),
            unit=f"Euro/({element.power_unit}*h)",
            source=self._source(element),
        )

    def get_energy_to_power_ratio_max(self, element: IndustryDSM) -> Attribute:
        """Shifting horizon of the carrier's category."""
        return element.energy_to_power_ratio_max.set_data(
            default_value=self._get_parameters(element)["energy_to_power_ratio_max"],
            unit="h",
            source=self._source(element),
        )

    def _get_cost(self, element: IndustryDSM, parameter: str) -> float:
        """Cost per tonne, per GWh for the carriers modeled on an energy basis."""
        cost = self._get_parameters(element)[parameter]
        if element.carrier not in ENERGY_CONTENT:
            return cost
        return cost / ENERGY_CONTENT[element.carrier]

    def _get_parameters(self, element: IndustryDSM) -> dict[str, float]:
        shiftability = element.settings.industry.dsm_shiftability
        return CATEGORY_PARAMETERS[int(self.data.at[element.carrier, shiftability])]

    def _source(self, element: IndustryDSM) -> AssumptionInformation:
        shiftability = element.settings.industry.dsm_shiftability
        category = self.data.at[element.carrier, shiftability]
        return AssumptionInformation(
            description=(
                f"{element.carrier}: demand-shiftability category {category} "
                f"({shiftability}, setting industry.dsm_shiftability), from a "
                f"literature review: {REFERENCES[element.carrier]}. The storage cost, "
                "variable cost and shifting horizon of the category are own "
                "assumptions, see docs, 'Demand-side management'."
            ),
        )
