from zen_creator import Sector

from zen_europe.elements.storage_technologies.industry_TES import (
    IndustryTESSteam150200Ceramic,
    IndustryTESSteam150200Food,
    IndustryTESSteam150200Glass,
    IndustryTESSteam150200Paper,
    IndustryTESWater0100Ceramic,
    IndustryTESWater0100Food,
    IndustryTESWater0100Glass,
    IndustryTESWater0100Paper,
    IndustryTESWater100150Ceramic,
    IndustryTESWater100150Food,
    IndustryTESWater100150Glass,
    IndustryTESWater100150Paper,
)


class IndustryTESSector(Sector):
    """Thermal energy storage of the industry heat sectors."""

    name = "industry_tes"
    required_sectors = ["industry_heat"]

    def __init__(self) -> None:
        super().__init__()
        self.elements = [
            IndustryTESWater0100Glass,
            IndustryTESWater100150Glass,
            IndustryTESSteam150200Glass,
            IndustryTESWater0100Ceramic,
            IndustryTESWater100150Ceramic,
            IndustryTESSteam150200Ceramic,
            IndustryTESWater0100Paper,
            IndustryTESWater100150Paper,
            IndustryTESSteam150200Paper,
            IndustryTESWater0100Food,
            IndustryTESWater100150Food,
            IndustryTESSteam150200Food,
        ]
