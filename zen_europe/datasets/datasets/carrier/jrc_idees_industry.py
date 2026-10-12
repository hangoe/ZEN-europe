from __future__ import annotations

from pathlib import Path

import pandas as pd
from zen_creator.datasets.datasets.dataset import Dataset
from zen_creator.datasets.datasets.metadata import MetaData

# the year columns of the first block of each sheet
FIRST_YEAR = 2000
LAST_YEAR = 2023
# sheet and rows of the production capacity and output per sector
CAPACITY_ROWS = {
    "glass": ("NMM", ["Glass production  (kt)"]),
    "ceramic": ("NMM", ["Ceramics & other NMM (kt bricks eq.)"]),
    "paper": (
        "PPA",
        [
            "Pulp production (kt)",
            "Paper production  (kt)",
            "Printing and media reproduction (kt paper eq.)",
        ],
    ),
}
# headers of the production sections in the NMM and PPA sheets
PRODUCTION_HEADERS = {
    "Physical output (kt)": "physical_output",
    "Installed capacity (kt production)": "installed_capacity",
}
# sheet and parent rows of the thermal final energy consumption per sector
THERMAL_ROWS = {
    "glass": ("NMM_fec", ["Glass: Thermal melting tank", "Glass: Annealing - thermal"]),
    "ceramic": (
        "NMM_fec",
        [
            "Ceramics: Thermal drying and sintering",
            "Ceramics: Steam drying and sintering",
            "Ceramics: Thermal kiln",
            "Ceramics: Thermal furnace",
        ],
    ),
    "paper": (
        "PPA_fec",
        [
            "Paper: Stock preparation - Thermal",
            "Paper: Paper machine - Steam use",
            "Paper: Product finishing - Steam use",
        ],
    ),
    "food": (
        "FBT_fec",
        [
            "Food: Direct Heat - Thermal",
            "Food: Process Heat - Thermal",
            "Food: Steam processing",
            "Food: Thermal drying",
            "Food: Steam drying",
            "Food: Steam cooling",
        ],
    ),
}
THERMAL_CARRIERS = {
    "Solids",
    "Refinery gas",
    "LPG",
    "Diesel oil and liquid biofuels",
    "Fuel oil",
    "Other liquids",
    "Natural gas and biogas",
    "Derived gases",
    "Biomass and waste",
    "Distributed steam",
}
SHEETS = ["NMM", "PPA", "NMM_fec", "PPA_fec", "FBT_fec"]


class JRCIDEESIndustry(Dataset[dict[str, pd.DataFrame]]):
    """
    JRC-IDEES industry dataset class.

    Production and thermal final energy consumption of the glass, ceramic, paper
    and food sectors, from the JRC-IDEES-2023 industry workbook of each country
    and of the EU27.
    """

    name = "jrc_idees_industry"

    def __init__(self, source_path: Path | str | None = None):
        super().__init__(source_path=source_path)

    def _set_metadata(self) -> MetaData:
        return MetaData(
            name=self.name,
            title=(
                "JRC-IDEES-2023: the Integrated Database of the European Energy System"
            ),
            author=[
                "Rózsai, M.",
                "Jaxa-Rozen, M.",
                "Salvucci, R.",
                "Sikora, P.",
                "Gea Bermudez, J.",
                "Neuwahl, F.",
            ],
            publication="Joint Research Centre (European Commission)",
            publication_year=2026,
            doi="10.2760/6945021",
            note="Industry workbooks, sheets NMM, PPA, NMM_fec, PPA_fec and FBT_fec.",
        )

    def _set_path(self) -> Path:
        if self.source_path is None:
            raise ValueError("source_path must be set to load the dataset.")
        return self.source_path / "02-carrier" / "industry" / "jrc_idees_industry"

    def _set_data(self) -> dict[str, pd.DataFrame]:
        thermal = {}
        production = {}
        for folder in sorted(self.path.iterdir()):
            if not folder.is_dir():
                continue
            workbook = folder / f"JRC-IDEES-2023_Industry_{folder.name}.xlsx"
            sheets = pd.read_excel(workbook, sheet_name=SHEETS, header=None)
            sheets = {sheet: self._extract_years(df) for sheet, df in sheets.items()}
            for sector, (sheet, parent_rows) in THERMAL_ROWS.items():
                thermal[(folder.name, sector)] = self._extract_thermal(
                    sheets[sheet], parent_rows)
            for sector, (sheet, rows) in CAPACITY_ROWS.items():
                production[(folder.name, sector)] = self._extract_production(
                    sheets[sheet], rows)
        return {
            # ktoe
            "thermal": pd.concat(thermal, names=["node", "sector", "carrier"]),
            # kt
            "production": pd.concat(production, names=["node", "sector", "quantity"]),
        }

    # -------- parsing ------------------------

    @staticmethod
    def _extract_years(sheet: pd.DataFrame) -> pd.DataFrame:
        """Return the first block of year columns, with the row labels as index."""
        data = sheet.iloc[:, 1:LAST_YEAR - FIRST_YEAR + 2]
        data.columns = range(FIRST_YEAR, LAST_YEAR + 1)
        data.index = sheet[0]
        return data

    @staticmethod
    def _extract_thermal(sheet: pd.DataFrame, parent_rows: list[str]) -> pd.DataFrame:
        """Sum the energy carrier rows below the parent rows of a sector.

        The first occurrence of a parent row is the consumption in ktoe, followed
        directly by its energy carrier rows.
        """
        labels = list(sheet.index)
        carrier_rows = []
        for parent in parent_rows:
            row = labels.index(parent) + 1
            while row < len(labels) and labels[row] in THERMAL_CARRIERS:
                carrier_rows.append(row)
                row += 1
        data = sheet.iloc[carrier_rows].astype(float)
        return data.groupby(level=0, sort=False).sum(min_count=1)

    @staticmethod
    def _extract_production(sheet: pd.DataFrame, rows: list[str]) -> pd.DataFrame:
        """Sum the sector's rows in the physical output and installed capacity
        sections."""
        labels = list(sheet.index)
        data = {}
        for header, quantity in PRODUCTION_HEADERS.items():
            start = labels.index(header) + 1
            # a section ends at the next "(kt production)" header
            end = next(
                (i for i in range(start, len(labels))
                 if isinstance(labels[i], str) and labels[i].endswith("(kt production)")),
                len(labels),
            )
            section = sheet.iloc[start:end]
            data[quantity] = section.loc[rows].astype(float).sum()
        return pd.DataFrame(data).T

    # -------- methods ------------------------

    def get_thermal_final_energy(self, sector: str, year: int) -> pd.DataFrame:
        """
        Get the thermal final energy consumption of a sector.

        Args:
            sector (str): The industry sector.
            year (int): The year of the data.

        Returns:
            pd.DataFrame: Consumption in ktoe, indexed by node, one column per
                energy carrier.
        """
        data = self.data["thermal"].xs(sector, level="sector")[year]
        if data.isna().any():
            raise ValueError(f"No {year} value for all thermal carriers of {sector}.")
        # carriers not reported for a node are not consumed there
        return data.unstack("carrier", fill_value=0.0)

    def get_installed_capacity(self, sector: str, year: int) -> pd.Series:
        """Installed production capacity (kt) per node."""
        return self.data["production"].xs(
            (sector, "installed_capacity"), level=["sector", "quantity"])[year]

    def get_physical_output(self, sector: str, year: int) -> pd.Series:
        """Physical production output (kt) per node."""
        return self.data["production"].xs(
            (sector, "physical_output"), level=["sector", "quantity"])[year]
