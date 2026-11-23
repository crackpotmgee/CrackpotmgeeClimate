import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).parents[1] / "custom_components" / "smartir"),
)

from software_auto import (  # noqa: E402
    COOL,
    HEAT,
    HEAT_COOL,
    OFF,
    SoftwareAutoModeGroup,
    select_group_mode,
    temperature_demand,
)


class SoftwareAutoDemandTests(unittest.TestCase):
    def test_temperature_demand_switches_at_range_edges(self):
        self.assertEqual(temperature_demand(19.0, 20.0, 22.0), (HEAT, 1.0))
        self.assertEqual(temperature_demand(23.0, 20.0, 22.0), (COOL, 1.0))
        self.assertIsNone(temperature_demand(21.0, 20.0, 22.0))
        self.assertIsNone(temperature_demand(None, 20.0, 22.0))

    def test_group_chooses_strongest_demand_and_holds_ties(self):
        demands = [(HEAT, 2.0), (COOL, 3.0)]
        self.assertEqual(select_group_mode(demands, HEAT), COOL)
        self.assertEqual(
            select_group_mode([(HEAT, 3.0), (COOL, 3.0)], HEAT),
            HEAT,
        )
        self.assertIsNone(
            select_group_mode([(HEAT, 3.0), (COOL, 3.0)], None)
        )


class FakeClimate:
    def __init__(self, unique_id, temperature, active_mode, timeline=None):
        self._unique_id = unique_id
        self._name = unique_id
        self._hvac_mode = HEAT_COOL
        self._current_temperature = temperature
        self._target_temperature_low = 20.0
        self._target_temperature_high = 22.0
        self._software_auto_active_mode = active_mode
        self.commands = []
        self.fail_when_turned_off = False
        self.timeline = timeline

    async def _async_apply_software_mode(
        self, mode, force=False, raise_on_error=False
    ):
        if mode == self._software_auto_active_mode and not force:
            return
        self.commands.append(mode)
        if self.timeline is not None:
            self.timeline.append((self._unique_id, mode))
        if mode == OFF and self.fail_when_turned_off:
            raise RuntimeError("simulated turn-off failure")
        self._software_auto_active_mode = mode


class SoftwareAutoGroupTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflicting_units_turn_off_before_new_mode_is_enabled(self):
        group = SoftwareAutoModeGroup()
        timeline = []
        heater = FakeClimate("heater", 19.0, HEAT, timeline)
        cooler = FakeClimate("cooler", 26.0, OFF, timeline)
        group.add(heater)
        group.add(cooler)
        group.current_mode = HEAT

        await group.async_update()

        self.assertEqual(group.current_mode, COOL)
        self.assertEqual(heater.commands, [OFF])
        self.assertEqual(cooler.commands, [COOL])
        self.assertLess(timeline.index(("heater", OFF)), timeline.index(("cooler", COOL)))

        cooler._current_temperature = 21.0
        await group.async_update()

        self.assertEqual(group.current_mode, HEAT)
        self.assertEqual(heater._software_auto_active_mode, HEAT)
        self.assertEqual(cooler._software_auto_active_mode, OFF)

    async def test_equal_conflicting_demands_keep_current_group_mode(self):
        group = SoftwareAutoModeGroup()
        heater = FakeClimate("heater", 18.0, HEAT)
        cooler = FakeClimate("cooler", 24.0, OFF)
        group.add(heater)
        group.add(cooler)
        group.current_mode = COOL

        await group.async_update()

        self.assertEqual(group.current_mode, COOL)
        self.assertEqual(heater.commands, [OFF])
        self.assertEqual(cooler.commands, [COOL])

    async def test_equal_conflicting_demands_without_prior_mode_turn_units_off(self):
        group = SoftwareAutoModeGroup()
        heater = FakeClimate("heater", 18.0, HEAT)
        cooler = FakeClimate("cooler", 24.0, COOL)
        group.add(heater)
        group.add(cooler)

        await group.async_update()

        self.assertIsNone(group.current_mode)
        self.assertEqual(heater.commands, [OFF])
        self.assertEqual(cooler.commands, [OFF])

    async def test_failed_turn_off_prevents_opposite_mode_activation(self):
        group = SoftwareAutoModeGroup()
        heater = FakeClimate("heater", 19.0, HEAT)
        cooler = FakeClimate("cooler", 25.0, OFF)
        heater.fail_when_turned_off = True
        group.add(heater)
        group.add(cooler)
        group.current_mode = HEAT

        with self.assertRaisesRegex(RuntimeError, "turn-off failure"):
            await group.async_update()

        self.assertEqual(heater.commands, [OFF])
        self.assertEqual(cooler.commands, [])


if __name__ == "__main__":
    unittest.main()
