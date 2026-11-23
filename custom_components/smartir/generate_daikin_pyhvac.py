#!/usr/bin/env python3
"""
Generate Daikin codes using the `pyhvac` library.

Usage examples:
  python -m custom_components.smartir.generate_daikin_pyhvac --model generic --mode cool --temp 24 --fan auto
"""

from __future__ import annotations

import argparse
import base64

from pyhvac import registry
from pyhvac.ir.formats import to_broadlink, to_pronto, to_raw
from pyhvac.state import HvacState


def try_pyhvac_generate(
    model: str,
    mode: str,
    temp: float | None,
    fan: str | None,
    swing: str | None,
    hswing: str | None,
    powerful: bool | None,
    output_format: str = "broadlink",
) -> str:
    """Generate an IR command in Broadlink Base64, Pronto, or raw format."""

    device = registry.get_device("daikin", model)
    if hswing not in (None, "off") and device.capabilities.swing_h is None:
        raise ValueError(f"Daikin model {model!r} does not support horizontal swing")

    mode = str(mode).lower()
    power = mode != "off"
    if not power:
        mode = "cool"

    state = HvacState(
        power=power,
        mode=mode,
        temperature=24.0 if temp is None else temp,
        fan=fan or "auto",
        swing_v=swing or "off",
        swing_h=hswing or "off",
        features={"powerful": powerful} if powerful is not None else {},
    )
    signal = device.encode(None, state).signal

    if output_format == "broadlink":
        return base64.b64encode(to_broadlink(signal)).decode("ascii")
    if output_format == "pronto":
        return to_pronto(signal)
    if output_format == "raw":
        return " ".join(str(pulse) for pulse in to_raw(signal))
    raise ValueError(f"Unsupported output format: {output_format}")


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main() -> None:
    p = argparse.ArgumentParser(description="Generate Daikin codes with pyhvac")
    p.add_argument(
        "--model", default="generic", help="Daikin model name supported by pyhvac"
    )
    p.add_argument(
        "--mode",
        default="cool",
        help="Operating mode: off, auto, cool, heat, dry, fan",
    )
    p.add_argument("--temp", type=float, default=24.0, help="Target temperature in Celsius")
    p.add_argument(
        "--fan", default="auto", help="Fan setting supported by the selected pyhvac model"
    )
    p.add_argument(
        "--format",
        default="broadlink",
        choices=("broadlink", "pronto", "raw"),
        help="Output format",
    )
    p.add_argument(
        "--swing", default=None, help="Vertical swing setting supported by the selected model"
    )
    p.add_argument(
        "--hswing",
        default=None,
        help="Horizontal swing setting supported by the selected model",
    )
    p.add_argument(
        "--powerful",
        type=_parse_bool,
        default=None,
        help="Enable or disable powerful mode",
    )
    args = p.parse_args()

    print(
        try_pyhvac_generate(
            args.model,
            args.mode,
            args.temp,
            args.fan,
            args.swing,
            args.hswing,
            args.powerful,
            args.format,
        )
    )


if __name__ == "__main__":
    main()
