from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.datasets.datasets.metadata import MetaData, SourceInformation
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

    def _source(self, element: IndustryDSM) -> SourceInformation:
        shiftability = element.settings.industry.dsm_shiftability
        category = self.data.at[element.carrier, shiftability]
        return SourceInformation(
            description=f"{element.carrier}: category {category} ({shiftability}).",
            metadata=self.metadata,
        )
