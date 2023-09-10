"""Select platform for eversolo."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

_EversoloDataUpdateCoordinatorT = TypeVar(
    '_EversoloDataUpdateCoordinatorT', bound=EversoloDataUpdateCoordinator
)


@dataclass
class EversoloSelectDescriptionMixin(Generic[_EversoloDataUpdateCoordinatorT]):
    """Mixin to describe a Select entity."""

    available_options: list[str]
    select_option: Callable[
        [_EversoloDataUpdateCoordinatorT], Coroutine[Any, Any, None]
    ]


@dataclass
class EversoloSelectDescription(
    SelectEntityDescription,
    EversoloSelectDescriptionMixin[_EversoloDataUpdateCoordinatorT],
):
    """Class to describe a Select entity."""


ENTITY_DESCRIPTIONS = [
    EversoloSelectDescription[EversoloDataUpdateCoordinator](
        key='vu_style',
        name='Eversolo VU Style',
        icon='mdi:gauge-low',
        available_options=['VU-Meter 1', 'VU-Meter 2', 'VU-Meter 3', 'VU-Meter 4'],
        select_option=lambda coordinator, option: coordinator.client.async_select_vu_mode_option(
            option
        ),
    )
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        EversoloSelect(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class EversoloSelect(EversoloEntity, SelectEntity):
    """Select to control Eversolo display brightness."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_options = self.entity_description.available_options
        self._attr_unique_id = (
            f'{coordinator.config_entry.entry_id}_{entity_description.key}'
        )

    @property
    def current_option(self) -> str:
        vu_mode_state = self.coordinator.data.get('vu_mode_state', None)

        if vu_mode_state is None:
            return None

        return self._attr_options[int(vu_mode_state['currentIndex'])]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        await self.entity_description.select_option(
            self.coordinator, self.entity_description.available_options.index(option)
        )
        self._attr_current_option = option
