from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.datasets.datasets.metadata import MetaData

from zen_europe.utils.utils import convert_country_names

logger = logging.getLogger(__name__)

WORKBOOK = "Eurostat_gross_heat_production_GWh.xlsx"
# sheet of the gross heat production per Eurostat fuel
SHEETS = {
    "natural_gas": "Sheet 22",
    "biomass": "Sheet 54",
    "electricity": "Sheet 69",
    "oil": "Sheet 23",
    "coal": "Sheet 2",
    "biogas": "Sheet 63",
    "industrial_waste": "Sheet 64",
    "renewable_municipal_waste": "Sheet 65",
    "non_renewable_municipal_waste": "Sheet 66",
}
# boiler fuel of each Eurostat fuel
BOILER_FUELS = {
    "natural_gas": "natural_gas",
    "biomass": "biomass",
    "biogas": "biomass",
    "electricity": "electricity",
    "oil": "oil",
    "coal": "coal",
    "industrial_waste": "waste",
    "renewable_municipal_waste": "waste",
    "non_renewable_municipal_waste": "waste",
}


class EurostatEnergyBalanceIndustry(Dataset[pd.DataFrame]):
    """
    Eurostat gross heat production dataset class.

    Gross heat production per fuel from the Eurostat energy balances (nrg_bal_c),
    exported to one sheet per fuel.
    """

    name = "eurostat_energy_balance_industry"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            title="Complete energy balances",
            author=["Eurostat"],
            publication="Eurostat",
            publication_year=2022,
            doi="10.2908/NRG_BAL_C",
            note="Gross heat production per fuel (GWh), extracts of nrg_bal_c.",
        )

    def _set_path(self) -> Path:
        if self.source_path is None:
            raise ValueError("source_path must be set to load the dataset.")
        return self.source_path / "02-carrier" / "industry" / WORKBOOK

    def _set_data(self) -> pd.DataFrame:
        sheets = pd.read_excel(self.path, sheet_name=list(SHEETS.values()), header=None)
        data = pd.concat(
            {fuel: self._extract_sheet(sheets[sheet]) for fuel, sheet in SHEETS.items()},
            names=["fuel", "node"],
        )
        return data  # GWh

    @staticmethod
    def _extract_sheet(sheet: pd.DataFrame) -> pd.DataFrame:
        """Extract the yearly values per node; every second column holds flags."""
        (header_row,) = sheet.index[sheet[0] == "TIME"]
        years = sheet.iloc[header_row, 1::2].dropna().astype(int)
        data = sheet.iloc[header_row + 1:, years.index]
        data.columns = years.to_numpy()
        data.index = convert_country_names(sheet.iloc[header_row + 1:, 0])
        data = data[data.index.notna()]
        # ":" marks missing values
        return data.replace(":", float("nan")).astype(float)

    def get_heat_production(self, year: int) -> pd.DataFrame:
        """
        Get the gross heat production per node and boiler fuel.

        The latest value up to `year` is used for each Eurostat fuel; biomass and
        biogas, and the three waste fuels are summed.

        Args:
            year (int): The latest year of the data.

        Returns:
            pd.DataFrame: Gross heat production in GWh, indexed by node, one column
                per boiler fuel.
        """
        data = self.data.loc[:, :year].ffill(axis=1)[year]
        for fuel, node in data[data.isna()].index:
            logger.warning(f"No {fuel} heat production for {node}; set to 0.")
        data = data.groupby([data.index.get_level_values("fuel").map(BOILER_FUELS),
                             data.index.get_level_values("node")]).sum()
        return data.unstack(0, fill_value=0.0)
