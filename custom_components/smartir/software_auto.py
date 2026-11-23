import asyncio
import math


OFF = "off"
HEAT = "heat"
COOL = "cool"
HEAT_COOL = "heat_cool"


def has_valid_temperature(temperature):
    return temperature is not None and math.isfinite(temperature)


def temperature_demand(temperature, low, high):
    if not has_valid_temperature(temperature):
        return None
    if temperature <= low:
        return HEAT, low - temperature
    if temperature >= high:
        return COOL, temperature - high
    return None


def select_group_mode(demands, current_mode):
    strongest = {
        HEAT: max((strength for mode, strength in demands if mode == HEAT), default=None),
        COOL: max((strength for mode, strength in demands if mode == COOL), default=None),
    }

    heat_strength = strongest[HEAT]
    cool_strength = strongest[COOL]
    if heat_strength is None:
        return COOL if cool_strength is not None else None
    if cool_strength is None:
        return HEAT
    if heat_strength > cool_strength:
        return HEAT
    if cool_strength > heat_strength:
        return COOL
    return current_mode if current_mode in (HEAT, COOL) else None


class SoftwareAutoModeGroup:
    def __init__(self):
        self.members = set()
        self.current_mode = None
        self._lock = asyncio.Lock()

    def add(self, entity):
        self.members.add(entity)

    def remove(self, entity):
        self.members.discard(entity)

    async def async_update(self, force_entity=None):
        async with self._lock:
            members = sorted(
                (
                    entity
                    for entity in self.members
                    if entity._hvac_mode == HEAT_COOL
                ),
                key=lambda entity: entity._unique_id or entity._name,
            )
            if not members:
                self.current_mode = None
                return

            restored_modes = {
                entity._software_auto_active_mode
                for entity in members
                if entity._software_auto_active_mode in (HEAT, COOL)
            }
            current_mode = self.current_mode
            if current_mode not in (HEAT, COOL) and len(restored_modes) == 1:
                current_mode = next(iter(restored_modes))

            demands_by_entity = {}
            demands = []
            for entity in members:
                demand = temperature_demand(
                    entity._current_temperature,
                    entity._target_temperature_low,
                    entity._target_temperature_high,
                )
                demands_by_entity[entity] = demand
                if demand is not None:
                    demands.append(demand)

            selected_mode = select_group_mode(demands, current_mode) or current_mode
            requested_modes = {}
            for entity in members:
                demand = demands_by_entity[entity]
                if (
                    selected_mode is not None
                    and (
                        (demand is not None and demand[0] == selected_mode)
                        or (
                            demand is None
                            and entity._software_auto_active_mode == selected_mode
                        )
                    )
                    and has_valid_temperature(entity._current_temperature)
                ):
                    requested_modes[entity] = selected_mode
                else:
                    requested_modes[entity] = OFF

            for entity in members:
                requested_mode = requested_modes[entity]
                if (
                    entity._software_auto_active_mode != requested_mode
                    and entity._software_auto_active_mode != OFF
                ):
                    await entity._async_apply_software_mode(
                        OFF, raise_on_error=True
                    )

            self.current_mode = selected_mode
            for entity in members:
                requested_mode = requested_modes[entity]
                if requested_mode != OFF:
                    await entity._async_apply_software_mode(
                        requested_mode,
                        force=entity is force_entity,
                        raise_on_error=True,
                    )
