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
    # every DSM is also listed by the sector of its product and is only added
    # when that sector is active as well
    required_sectors = []

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
