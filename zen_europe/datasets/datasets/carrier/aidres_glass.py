from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.datasets.datasets.metadata import MetaData, SourceInformation
from zen_creator.utils.attribute import Attribute

if TYPE_CHECKING:
    from zen_europe.elements.conversion_technologies.kiln_fuel_industry import (
        KilnFuelIndustry,
    )

# kiln fuel input per kiln fuel output of the glass routes, weighted by production
# share, relative to the natural gas route; also used for ceramic (see docu)
KILN_FUEL_INPUT = {"natural_gas": 1.0, "hydrogen": 1.0577, "electricity": 0.8438}


class AIDRESGlass(Dataset[pd.DataFrame]):
    """Energy intensity and EU production share of the glass production routes."""

    name = "aidres_glass"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            title=(
                "AIDRES: Advancing industrial decarbonization by assessing the future "
                "use of renewable energies in industrial processes"
            ),
            author=["European Commission, Directorate-General for Energy"],
            publication="Publications Office of the European Union",
            publication_year=2023,
            doi="10.2833/696697",
            note="Glass routes (container, flat, fibre), Tables 19, 21 and 23.",
        )

    def _set_path(self) -> Path:
        if self.source_path is None:
            raise ValueError("source_path must be set to load the dataset.")
        return self.source_path / "02-carrier" / "industry" / "AIDRES2023_glass.csv"

    def _set_data(self) -> pd.DataFrame:
        return pd.read_csv(self.path).set_index("sub_process")

    def get_sub_processes(self) -> pd.DataFrame:
        """Natural gas and electricity intensity (GJ/t) per glass route."""
        return self.data[["ng_GJ_t", "elec_GJ_t"]]

    def get_production_shares(self) -> pd.Series:
        """EU production share per glass route."""
        return self.data["eu_production_share"]

    def get_conversion_factor_kiln_fuel(self, element: KilnFuelIndustry) -> Attribute:
        """Fuel input per kiln fuel, relative to the natural gas route."""
        return element.conversion_factor.set_data(
            default_value=[
                {
                    element.fuel: {
                        "default_value": KILN_FUEL_INPUT[element.fuel],
                        "unit": "GW/GW",
                    }
                }
            ],
            source=SourceInformation(
                description="Fuel route efficiency of the glass routes.",
                metadata=self.metadata,
            ),
        )
