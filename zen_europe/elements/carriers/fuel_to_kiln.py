from zen_creator.elements import Carrier

from zen_europe.elements.carriers.heat_industry import HeatIndustry


class FuelToKilnGlass(HeatIndustry, Carrier):
    name: str = "fuel_to_kiln_glass"


class FuelToKilnCeramic(HeatIndustry, Carrier):
    name: str = "fuel_to_kiln_ceramic"
