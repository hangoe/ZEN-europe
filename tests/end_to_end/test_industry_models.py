"""End-to-end tests of the industry heat model variants in data/models.yaml."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from zen_creator import Model

from zen_europe.model_creator import DATA_PATH, create_model

SECTORS = ("glass", "ceramic", "paper", "food")


def _create(name: str) -> Model:
    return create_model(models=DATA_PATH / "models.yaml", model_name=name, write=False)


@pytest.fixture(scope="module")
def full() -> Model:
    return _create("zen_europe_ind_heat_v1_full_flexibility")


def test_elements_per_sector(full: Model) -> None:
    names = set(full.elements)
    for sector in SECTORS:
        assert {
            f"heat_industry_{b}_{sector}" for b in ("0_100", "100_150", "150_200")
        } <= names
        assert (
            sum(
                n.startswith("heat_pump_industry") and n.endswith(sector) for n in names
            )
            == 6
        )
        assert sum(n.endswith(f"_boiler_industry_{sector}") for n in names) == 6
        assert {f"industry_TES_steam_150_200_{sector}", f"{sector}_DSM"} <= names
        has_kiln = f"natural_gas_to_kilnfuel_{sector}" in names
        assert has_kiln == (sector in ("glass", "ceramic"))
    assert {"glass_post_comb", "ceramic_post_comb", "clinker_DSM"} <= names


def test_base() -> None:
    model = _create("zen_europe_base")
    assert not any(
        any(sector in n for sector in SECTORS) or "TES" in n or n.endswith("_DSM")
        for n in model.elements
    )


def test_no_flexibility_and_no_diffusion() -> None:
    model = _create("zen_europe_ind_heat_v1_no_flexibility_nodiffusion")
    assert not any("TES" in n or n.endswith("_DSM") for n in model.elements)
    heat_pump = model.elements["heat_pump_industry_150_200_water_paper"]
    assert heat_pump.max_diffusion_rate.default_value == np.inf


def test_single_temperature_level() -> None:
    model = _create("zen_europe_ind_heat_v1_full_flexibility_single_temp")
    names = set(model.elements)
    assert "heat_pump_industry_150_200_water_glass" in names
    assert "heat_pump_industry_0_100_water_glass" not in names


def test_write(tmp_path: Path) -> None:
    create_model(
        models=DATA_PATH / "models.yaml",
        model_name="zen_europe_ind_heat_v1_no_flexibility",
        output_folder=tmp_path,
    )
    boiler = (
        tmp_path
        / "zen_europe_ind_heat_v1_no_flexibility"
        / "set_technologies"
        / "set_conversion_technologies"
        / "natural_gas_boiler_industry_glass"
    )
    assert (boiler / "capacity_existing.csv").exists()


def test_industry_heat_without_carbon_and_cement(tmp_path: Path) -> None:
    """The post-combustion capture is declared by industry_heat, carbon and cement,
    and the DSM by industry_dsm and the product's sector, so neither is added."""
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n"
        "  no_carbon:\n"
        "    settings:\n"
        "      structure:\n"
        "        set_sectors: [electricity, gas, heat, district_heating, hydrogen,"
        " industry_heat]\n"
    )
    model = create_model(models=models, model_name="no_carbon", write=False)
    names = set(model.elements)
    assert {"glass_production", "natural_gas_to_kilnfuel_glass"} <= names
    assert not any(n.endswith("_post_comb") or n.endswith("_DSM") for n in names)
