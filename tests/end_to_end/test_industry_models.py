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
    return _create("zen_europe_base")


def _is_flexibility(name: str) -> bool:
    return "TES" in name or name.endswith("_DSM")


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
    assert {
        "glass_post_comb",
        "ceramic_post_comb",
        "clinker_DSM",
        "ammonia_DSM",
    } <= names


def test_no_industry_heat() -> None:
    model = _create("zen_europe_no_industry_heat")
    assert not any(
        any(sector in n for sector in SECTORS) or _is_flexibility(n)
        for n in model.elements
    )


def test_no_flexibility_and_no_diffusion() -> None:
    model = _create("zen_europe_ind_heat_no_flexibility_nodiffusion")
    assert "glass_production" in model.elements
    assert not any(_is_flexibility(n) for n in model.elements)
    heat_pump = model.elements["heat_pump_industry_150_200_water_paper"]
    assert heat_pump.max_diffusion_rate.default_value == np.inf


def test_tes_only_and_dsm_only() -> None:
    tes_only = set(_create("zen_europe_ind_heat_TES_only").elements)
    assert "industry_TES_steam_150_200_glass" in tes_only
    assert not any(n.endswith("_DSM") for n in tes_only)
    dsm_only = set(_create("zen_europe_ind_heat_DSM_only").elements)
    assert {"glass_DSM", "ammonia_DSM"} <= dsm_only
    assert not any("TES" in n for n in dsm_only)


def test_single_temperature_level() -> None:
    model = _create("zen_europe_ind_heat_single_temp")
    names = set(model.elements)
    assert "heat_pump_industry_150_200_water_glass" in names
    assert "heat_pump_industry_0_100_water_glass" not in names
    assert "heat_pump_industry_100_150_waste_heat_food" not in names


def test_write(tmp_path: Path) -> None:
    create_model(
        models=DATA_PATH / "models.yaml",
        model_name="zen_europe_ind_heat_no_flexibility",
        output_folder=tmp_path,
    )
    boiler = (
        tmp_path
        / "zen_europe_ind_heat_no_flexibility"
        / "set_technologies"
        / "set_conversion_technologies"
        / "natural_gas_boiler_industry_glass"
    )
    assert (boiler / "capacity_existing.csv").exists()


def _create_with_sectors(tmp_path: Path, sectors: str) -> Model:
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n"
        "  subset:\n"
        "    settings:\n"
        "      structure:\n"
        f"        set_sectors: [{sectors}]\n"
    )
    return create_model(models=models, model_name="subset", write=False)


def test_glass_without_carbon_and_cement(tmp_path: Path) -> None:
    """The post-combustion capture is declared by glass, carbon and cement, so it is
    not added; the DSM is declared by glass only."""
    names = set(
        _create_with_sectors(
            tmp_path, "electricity, gas, heat, district_heating, hydrogen, glass"
        ).elements
    )
    assert {"glass_production", "natural_gas_to_kilnfuel_glass", "glass_DSM"} <= names
    assert not any(n.endswith("_post_comb") for n in names)
    assert not any("ceramic" in n or "paper" in n for n in names)


def test_paper_without_hydrogen(tmp_path: Path) -> None:
    names = set(
        _create_with_sectors(
            tmp_path, "electricity, gas, heat, district_heating, paper"
        ).elements
    )
    assert {"paper_production", "paper_DSM", "industry_TES_water_0_100_paper"} <= names
