from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from zen_creator.datasets.datasets.metadata import AssumptionInformation
from zen_creator.elements import Carrier
from zen_creator.utils.attribute import Attribute

if TYPE_CHECKING:
    from zen_creator.model import Model


class FuelToKiln:
    """Kiln fuel of the glass or ceramic sector (natural gas, hydrogen, electricity)."""

    def __init__(self, model: Model, power_unit: str = "GW"):
        super().__init__(model=model, power_unit=power_unit)

    def _set_availability_export_yearly(self) -> Attribute:
        """Unlimited yearly export."""
        return self.availability_export_yearly.set_data(
            default_value=np.inf,
            unit="GWh",
            source=AssumptionInformation(description="No export limit."),
        )


class FuelToKilnGlass(FuelToKiln, Carrier):
    name: str = "fuel_to_kiln_glass"


class FuelToKilnCeramic(FuelToKiln, Carrier):
    name: str = "fuel_to_kiln_ceramic"
