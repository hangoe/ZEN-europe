from zen_creator import Sector

from zen_europe.elements.storage_technologies.industry_DSM import (
    AmmoniaDSM,
    CeramicDSM,
    ClinkerDSM,
    FoodDSM,
    GlassDSM,
    MethanolDSM,
    OlefinDSM,
    PaperDSM,
    PrimarySteelDSM,
    SecondarySteelDSM,
)


class IndustryDSMSector(Sector):
    """Demand-side management of industrial products."""

    name = "industry_dsm"
    required_sectors = ["industry_heat", "ammonia", "cement", "methanol", "steel"]

    def __init__(self) -> None:
        super().__init__()
        self.elements = [
            GlassDSM,
            CeramicDSM,
            PaperDSM,
            FoodDSM,
            AmmoniaDSM,
            ClinkerDSM,
            MethanolDSM,
            PrimarySteelDSM,
            SecondarySteelDSM,
            OlefinDSM,
        ]
