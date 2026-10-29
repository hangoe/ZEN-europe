from zen_creator import Sector

from zen_europe.elements.carriers.fuel_to_kiln import (
    FuelToKilnGlass,
)
from zen_europe.elements.carriers.heat_industry import (
    HeatIndustry0100Glass,
    HeatIndustry100150Glass,
    HeatIndustry150200Glass,
)
from zen_europe.elements.carriers.industry_products import (
    Glass,
)
from zen_europe.elements.conversion_technologies.boiler_industry import (
    BiomassBoilerIndustryGlass,
    CoalBoilerIndustryGlass,
    ElectrodeBoilerIndustryGlass,
    NaturalGasBoilerIndustryGlass,
    OilBoilerIndustryGlass,
    WasteBoilerIndustryGlass,
)
from zen_europe.elements.conversion_technologies.heat_industry_temp_conversion import (
    HeatIndustryTempConversion100Glass,
    HeatIndustryTempConversion150Glass,
)
from zen_europe.elements.conversion_technologies.heat_pump_industry import (
    HeatPumpIndustry0100WasteHeatGlass,
    HeatPumpIndustry0100WaterGlass,
    HeatPumpIndustry100150WasteHeatGlass,
    HeatPumpIndustry100150WaterGlass,
    HeatPumpIndustry150200WasteHeatGlass,
    HeatPumpIndustry150200WaterGlass,
)
from zen_europe.elements.conversion_technologies.industry_production import (
    GlassProduction,
)
from zen_europe.elements.conversion_technologies.kiln_fuel_industry import (
    ElectricityToKilnfuelGlass,
    HydrogenToKilnfuelGlass,
    NaturalGasToKilnfuelGlass,
)
from zen_europe.elements.retrofitting_technologies.industry_post_comb import (
    GlassPostComb,
)
from zen_europe.elements.storage_technologies.industry_DSM import (
    GlassDSM,
)
from zen_europe.elements.storage_technologies.industry_TES import (
    IndustryTESSteam150200Glass,
    IndustryTESWater0100Glass,
    IndustryTESWater100150Glass,
)


class GlassSector(Sector):
    """Glass production and its process heat supply.

    The sector has its own heat carriers and heat technologies, so heat is never
    shared with the other industry sectors.
    """

    name = "glass"
    required_sectors = [
        "electricity",
        "gas",
        "hydrogen",
        "district_heating",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.elements = [
            Glass,
            GlassProduction,
            GlassPostComb,
            HeatIndustry0100Glass,
            HeatIndustry100150Glass,
            HeatIndustry150200Glass,
            FuelToKilnGlass,
            HeatPumpIndustry0100WasteHeatGlass,
            HeatPumpIndustry0100WaterGlass,
            HeatPumpIndustry100150WasteHeatGlass,
            HeatPumpIndustry100150WaterGlass,
            HeatPumpIndustry150200WasteHeatGlass,
            HeatPumpIndustry150200WaterGlass,
            BiomassBoilerIndustryGlass,
            ElectrodeBoilerIndustryGlass,
            NaturalGasBoilerIndustryGlass,
            OilBoilerIndustryGlass,
            CoalBoilerIndustryGlass,
            WasteBoilerIndustryGlass,
            HeatIndustryTempConversion150Glass,
            HeatIndustryTempConversion100Glass,
            NaturalGasToKilnfuelGlass,
            HydrogenToKilnfuelGlass,
            ElectricityToKilnfuelGlass,
            IndustryTESWater0100Glass,
            IndustryTESWater100150Glass,
            IndustryTESSteam150200Glass,
            GlassDSM,
        ]
