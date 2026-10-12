from typing import ClassVar, Literal

from zen_creator.utils.settings import SettingsCategory


class IndustrySettings(SettingsCategory):
    """Industry heat, production and flexibility settings."""

    name: ClassVar[str] = "industry"

    # year of the production, energy and heat statistics
    data_year: int = 2023
    # full-load hours of the production plants and boilers
    operating_hours: int = 8000
    # fuels below this share of a sector's fuel mix are dropped
    fuel_share_cutoff: float = 0.10
    # capacity limit of the zero-cost pass-through technologies, as a multiple of
    # the flat demand they serve (techs: heat temp conversion, _to_kilnfuel techs)
    capacity_limit_margin: float = 2.0
    # existing boiler capacities below this value (GW per node) are set to zero
    min_boiler_capacity: float = 0.005
    dsm_shiftability: Literal["optimistic", "pessimistic"] = "optimistic"
