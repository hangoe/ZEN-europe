"""Names and helpers shared by the industry heat sectors, see docs, "Industry heat
sectors"."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zen_europe.utils.utils import (
    calculate_capacity_addition_from_cumulative,
    format_capacity_existing,
)

if TYPE_CHECKING:
    import pandas as pd
    from zen_creator import Element, Model

# year of the production, energy and heat statistics
DATA_YEAR = 2023
SECTORS = ("glass", "ceramic", "paper", "food")
# sectors whose > 200 °C natural gas can switch kiln fuel
KILN_SECTORS = ("glass", "ceramic")
HEAT_LEVELS = ("0_100", "100_150", "150_200")
HEAT_SOURCES = ("waste_heat", "water")
BOILER_FUELS = ("biomass", "natural_gas", "electrode", "oil", "coal", "waste")


def heat_carrier(level: str, sector: str) -> str:
    """Heat carrier of a sector's temperature band."""
    return f"heat_industry_{level}_{sector}"


def kiln_fuel(sector: str) -> str:
    """Kiln fuel carrier of a sector."""
    return f"fuel_to_kiln_{sector}"


def model_nodes(element: Element) -> tuple[str, ...]:
    """Nodes of the element's model."""
    return tuple(element.model.config.system.set_nodes)


def spread_capacity_existing(capacity: pd.Series, element: Element) -> pd.Series:
    """Spread today's capacity per node over its construction years, as for all
    other technologies."""
    frame = capacity.to_frame(element.settings.time.reference_year - 1)
    frame = calculate_capacity_addition_from_cumulative(frame, element)
    return format_capacity_existing(frame)


def remove_inactive_industry_elements(model: Model) -> None:
    """Remove the TES, DSM and industry heat pumps that are switched off in the
    `industry_flexibility` settings."""
    # imported here, the element modules import this module
    from zen_europe.elements.conversion_technologies.heat_pump_industry import (
        HeatPumpIndustry,
    )
    from zen_europe.elements.storage_technologies.industry_DSM import IndustryDSM
    from zen_europe.elements.storage_technologies.industry_TES import IndustryTES

    settings = model.settings.industry_flexibility
    inactive = [
        name
        for name, element in model.elements.items()
        if (isinstance(element, IndustryTES) and not settings.use_tes)
        or (isinstance(element, IndustryDSM) and settings.dsm_shiftability == "none")
        or (
            isinstance(element, HeatPumpIndustry)
            and element.temp_level not in settings.heat_pump_temp_levels
        )
    ]
    for name in inactive:
        model.remove_element_by_name(name)
