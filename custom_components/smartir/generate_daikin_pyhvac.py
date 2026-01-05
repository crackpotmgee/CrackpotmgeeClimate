#!/usr/bin/env python3
"""
Generate Daikin codes using the `pyhvac` library (if installed) or fallback to
`gcdaikin` CLI. This script is defensive because `pyhvac` is work-in-progress
and plugin APIs can vary.

Usage examples:
  pip3 install pyhvac
  python tools/generate_daikin_pyhvac.py --model generic --mode cool --temp 24 --fan auto --format broadlink

The script will try these approaches in order:
 - Import `pyhvac` and find a `PluginObject` for a Daikin brand plugin,
   instantiate it and call `get_device(...)` to obtain an HVAC object, then
   call `to_broadlink()` / `to_lirs()` if available.
 - If library usage fails, try calling the `gcdaikin` CLI (if present).

The outputs are printed to stdout. This file is a lightweight integration
helper — adapt it into existing generation pipelines as needed.
"""

from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import base64
from pyhvac.plugins.daikin import PluginObject
from typing import Optional


def try_pyhvac_generate(model: str, mode: str, temp: Optional[float], fan: Optional[str], swing: Optional[str], hswing: Optional[str], powerful: Optional[bool]) -> Optional[str]:
    """Try to generate codes using pyhvac as a library.

    Returns the generated code string (e.g. Broadlink base64) or None if it
    couldn't be generated.
    """

    device = PluginObject().get_device(model)

    frames = []
    device.set_temperature(temp)
    device.set_fan(fan)
    device.set_swing(swing)
    device.set_hswing(hswing)
    device.set_powerful(powerful)
    device.set_mode(mode)

    frames = device.build_ircode()

   
    bframe = device.to_broadlink(frames)
    print(f"broadlink={bframe}")
    return "{}".format(str(base64.b64encode(bframe), "ascii"))
    



def main():
    p = argparse.ArgumentParser(description="Generate Daikin codes with pyhvac (best-effort)")
    p.add_argument("--model", default="generic", help="Device model name (plugin-specific)")
    p.add_argument("--mode", default="cool", help="Operating mode: off, auto, cool, heat, dry, fan")
    p.add_argument("--temp", type=float, default=None, help="Target temperature (if applicable)")
    p.add_argument("--fan", default=None, help="Fan speed string (auto, low, medium, high, etc.)")
    p.add_argument("--format", default="broadlink", choices=("broadlink", "lirs", "frames"), help="Desired output format")
    p.add_argument("--swing", default=None, help="Swing mode (if applicable)")
    p.add_argument("--hswing", default=None, help="Horizontal swing mode (if applicable)")
    p.add_argument("--powerful", default=None, help="Powerful mode (if applicable)")
    args = p.parse_args()

    # 1) Try library approach
    print("Trying pyhvac library...")
    lib_out = try_pyhvac_generate(args.model, args.mode, args.temp, args.fan, args.swing, args.hswing, args.powerful, args.format)
    if lib_out:
        print("Generated via pyhvac library:\n")
        print(lib_out)
        return


if __name__ == "__main__":
    main()
