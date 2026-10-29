from __future__ import annotations

from pathlib import Path

import pandas as pd
from zen_creator import Dataset
from zen_creator.datasets.datasets.metadata import MetaData

# Emissions are reported in kt, the carbon budget is accounted in Gt.
_KT_PER_GT = 1e6
# ZEN-europe sector of each ONS industry
_SECTOR_ROWS = {
    "paper": "paper (SIC 17)",
    "food": "food, beverages and tobacco (SIC 10-12)",
}


class ONSIndustryEmissions(Dataset[pd.DataFrame]):
    """CO2 emissions of the UK paper and food industries, as reported by the ONS."""

    name = "ons_industry_emissions"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            title=(
                "Atmospheric emissions: greenhouse gases by industry and gas, "
                "United Kingdom"
            ),
            author=["Office for National Statistics"],
            publication="ONS",
            publication_year=2026,
            url=(
                "https://www.ons.gov.uk/economy/environmentalaccounts/datasets/"
                "ukenvironmentalaccountsatmosphericemissionsgreenhousegasemissions"
                "byeconomicsectorandgasunitedkingdom"
            ),
            note="Sheet CO2, SIC 17 and SIC 10-12 (summed), UK residence basis.",
        )

    def _set_path(self) -> Path:
        return (
            self.source_path
            / "01-energy_system"
            / "ons_industry_emissions"
            / "ons_industry_emissions_co2.csv"
        )

    def _set_data(self) -> pd.DataFrame:
        data = pd.read_csv(self.path, index_col="industry")
        data.columns = data.columns.astype(int)
        data.columns.name = "year"
        return data

    def get_emissions_sectors(self, sectors: list[str]) -> pd.DataFrame:
        """Emissions in Gt of the modeled sectors among `paper` and `food`."""
        rows = [row for sector, row in _SECTOR_ROWS.items() if sector in sectors]
        return self.data.loc[rows] / _KT_PER_GT
