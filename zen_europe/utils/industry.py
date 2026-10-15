"""Names shared by the industry heat sectors, see docs, "Industry heat sectors"."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zen_creator import Element

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
