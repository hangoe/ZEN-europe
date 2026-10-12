# Import concrete settings categories to register them (side effect) with
# zen_creator's SettingsCategory registry, so they become queryable as
# model.settings.<name> (e.g. model.settings.time).
from .availability import AvailabilitySettings  # noqa: F401
from .cache import CacheSettings  # noqa: F401
from .cost import CostSettings  # noqa: F401
from .data_source import DataSourceSettings  # noqa: F401
from .emissions import EmissionsSettings  # noqa: F401
from .industry import IndustrySettings  # noqa: F401
from .investment import InvestmentSettings  # noqa: F401
from .max_load import MaxLoadSettings  # noqa: F401
from .region import RegionSettings  # noqa: F401
from .scenario import ScenarioSettings  # noqa: F401
from .structure import StructureSettings  # noqa: F401
from .time import TimeSettings  # noqa: F401

__all__ = [
    "TimeSettings",
    "InvestmentSettings",
    "IndustrySettings",
    "CostSettings",
    "EmissionsSettings",
    "DataSourceSettings",
    "AvailabilitySettings",
    "MaxLoadSettings",
    "ScenarioSettings",
    "CacheSettings",
    "RegionSettings",
    "StructureSettings",
]
