"""Select platform for eversolo."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN, LOGGER
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

_EversoloDataUpdateCoordinatorT = TypeVar(
    "_EversoloDataUpdateCoordinatorT", bound=EversoloDataUpdateCoordinator
)


@dataclass
class EversoloSelectDescriptionMixin(Generic[_EversoloDataUpdateCoordinatorT]):
    """Mixin to describe a Select entity."""

    get_selected_option: Callable[[_EversoloDataUpdateCoordinatorT], int]
    get_available_options: Callable[[
        _EversoloDataUpdateCoordinatorT], list[dict]]
    select_option: Callable[
        [_EversoloDataUpdateCoordinatorT, int, str], Coroutine[Any, Any, None]
    ]


@dataclass
class EversoloSelectDescription(
    SelectEntityDescription,
    EversoloSelectDescriptionMixin[_EversoloDataUpdateCoordinatorT],
):
    """Class to describe a Select entity."""


ENTITY_DESCRIPTIONS = [
    EversoloSelectDescription[EversoloDataUpdateCoordinator](
        key="vu_style",
        name="VU Style",
        icon="mdi:gauge-low",
        get_selected_option=lambda coordinator: coordinator.data.get(
            "vu_mode_state", {}
        ).get("currentIndex", -1),
        get_available_options=lambda coordinator: coordinator.data.get(
            "vu_mode_state", {}
        ).get("data", None),
        select_option=lambda coordinator, index, tag: coordinator.client.async_select_vu_mode_option(
            index, tag
        ),
    ),
    EversoloSelectDescription[EversoloDataUpdateCoordinator](
        key="spectrum_style",
        name="Spectrum Style",
        icon="mdi:chart-histogram",
        get_selected_option=lambda coordinator: coordinator.data.get(
            "spectrum_mode_state", {}
        ).get("currentIndex", -1),
        get_available_options=lambda coordinator: coordinator.data.get(
            "spectrum_mode_state", {}
        ).get("data", None),
        select_option=lambda coordinator, index, tag: coordinator.client.async_select_spectrum_mode_option(
            index, tag
        ),
    ),
    EversoloSelectDescription[EversoloDataUpdateCoordinator](
        key="output_mode",
        name="Output Mode",
        icon="mdi:export",
        get_selected_option=lambda coordinator: coordinator.data.get(
            "input_output_state", {}
        ).get("outputIndex", -1),
        get_available_options=lambda coordinator: coordinator.data.get(
            "input_output_state", {}
        ).get("transformed_outputs", None),
        select_option=lambda coordinator, index, tag: coordinator.client.async_set_output(
            index, tag
        ),
    ),
]

KNOB_COLOR_DESCRIPTION = EversoloSelectDescription[EversoloDataUpdateCoordinator](
    key="knob_color",
    name="Knob Color",
    icon="mdi:palette",
    get_selected_option=lambda coordinator: coordinator.data.get(
        "knob_color_state", {}
    ).get("currentIndex", -1),
    get_available_options=lambda coordinator: coordinator.data.get(
        "knob_color_state", {}
    ).get("data", None),
    select_option=lambda coordinator, index, tag: coordinator.client.async_select_knob_color_option(
        index, tag
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the Select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    descriptions = list(ENTITY_DESCRIPTIONS)
    if "knob_color_state" in coordinator.data:
        descriptions.append(KNOB_COLOR_DESCRIPTION)

    entities = [
        EversoloSelect(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in descriptions
    ]
    
    # Append the dedicated Input Mode entity that handles flat dictionaries
    entities.append(EversoloInputSelectEntity(coordinator))

    async_add_devices(entities)


class EversoloSelect(EversoloEntity, SelectEntity):
    """Select to control Eversolo Selects."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the Select class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        options = self.entity_description.get_available_options(
            self.coordinator)

        if options is None:
            LOGGER.debug("No options found")
            return []

        return [options[i].get("title", "") for i in range(len(options))]

    @property
    def current_option(self) -> str:
        """Return current state."""
        current_index = self.entity_description.get_selected_option(
            self.coordinator)

        if current_index < 0 or current_index >= len(self.options):
            LOGGER.debug("Current index %s is out of range", current_index)
            return None

        return list(self.options)[current_index]

    async def async_select_option(self, option: str) -> None:
        """Change to selected option."""

        options = self.entity_description.get_available_options(
            self.coordinator)

        if options is None:
            LOGGER.error("No options found")
            return

        index, tag = None, None
        for i, value in enumerate(options):
            if option == value.get("title", None):
                index, tag = i, value.get("tag", "")
                break

        if index is None or tag is None:
            LOGGER.debug("Option %s not found", option)
            return

        await self.entity_description.select_option(self.coordinator, index, tag)
        self._attr_current_option = option


class EversoloInputSelectEntity(EversoloEntity, SelectEntity):
    """Eversolo Input Mode Select."""

    def __init__(self, coordinator: EversoloDataUpdateCoordinator):
        """Initialize the select."""
        super().__init__(coordinator)
        self._attr_name = "Input Mode"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_input_mode"
        self._attr_icon = "mdi:import"

    @property
    def options(self) -> list[str]:
        """Return available options."""
        sources = self.coordinator.data.get("input_output_state", {}).get(
            "transformed_sources", None
        )
        if sources is None:
            return []
        return list(sources.values())

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        input_output_state = self.coordinator.data.get("input_output_state", None)
        if input_output_state is None:
            return None

        sources = input_output_state.get("transformed_sources", None)
        if sources is None:
            return None

        input_index = input_output_state.get("inputIndex", -1)
        if input_index < 0 or input_index >= len(sources):
            return None

        return list(sources.values())[input_index]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        sources = self.coordinator.data.get("input_output_state", {}).get(
            "transformed_sources", None
        )
        if sources is None:
            return

        index = next(
            (i for i, (k, v) in enumerate(sources.items()) if v == option), None
        )
        tag = next((k for k, v in sources.items() if v == option), None)

        if index is not None and tag is not None:
            await self.coordinator.client.async_set_input(index, tag)
            await self.coordinator.async_request_refresh()
