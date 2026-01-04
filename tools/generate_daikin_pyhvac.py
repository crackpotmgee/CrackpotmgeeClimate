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
from typing import Optional


def try_pyhvac_generate(model: str, mode: str, temp: Optional[float], fan: Optional[str], fmt: str) -> Optional[str]:
    """Try to generate codes using pyhvac as a library.

    Returns the generated code string (e.g. Broadlink base64) or None if it
    couldn't be generated.
    """
    try:
        import pyhvac  # type: ignore
    except Exception as e:
        print(f"pyhvac import failed: {e}")
        return None

    # Try to find a daikin plugin module under pyhvac.plugins
    plugin_mod = None
    try:
        # Many plugins are available as submodules, try the common name
        plugin_mod = importlib.import_module("pyhvac.plugins.daikin")
    except Exception:
        # Fallback: iterate submodules if package exposes them
        try:
            plugins_pkg = importlib.import_module("pyhvac.plugins")
            for attr in dir(plugins_pkg):
                if attr.lower().startswith("daik"):
                    try:
                        plugin_mod = importlib.import_module(f"pyhvac.plugins.{attr}")
                        break
                    except Exception:
                        continue
        except Exception:
            plugin_mod = None

    if not plugin_mod:
        print("No daikin plugin module found inside pyhvac.plugins")
        return None

    # PluginObject is the expected entrypoint class
    PluginObject = getattr(plugin_mod, "PluginObject", None)
    if PluginObject is None:
        print("daikin plugin does not expose PluginObject class")
        return None

    try:
        plugin = PluginObject()
    except TypeError:
        # Maybe PluginObject is a module-level object
        plugin = PluginObject

    # Try to call get_device(model) or get_device() depending on plugin
    get_device = getattr(plugin, "get_device", None)
    if get_device is None:
        print("PluginObject has no get_device(...) method")
        return None

    try:
        # Many plugins expect model name; some return a dict of models instead
        device = get_device(model)
    except TypeError:
        # Try without args
        device = get_device()
    except Exception as e:
        print(f"get_device raised: {e}")
        return None

    # The returned device is expected to provide helper methods like
    # `to_broadlink()` or `to_lirs()`; try them in preference order.
    for method_name in ("to_broadlink", "to_lirs", "to_frames"):
        method = getattr(device, method_name, None)
        if method is None:
            continue
        try:
            # Build a simple state dict. pyhvac plugins expect canonical names
            # such as `mode`, `temperature`, `fan`, `swing` etc.
            state = {"mode": mode}
            if temp is not None:
                state["temperature"] = temp
            if fan:
                state["fan"] = fan

            # Some implementations expect keyword args, others a dict
            try:
                result = method(**state)
            except TypeError:
                result = method(state)

            # Normalise bytes -> str
            if isinstance(result, bytes):
                return result.decode("ascii", errors="ignore")
            return str(result)
        except Exception as e:
            print(f"Calling {method_name} failed: {e}")
            continue

    print("Device object doesn't expose to_broadlink/to_lirs/to_frames methods")
    return None


def try_cli_gcdaikin(args: argparse.Namespace) -> Optional[str]:
    """Try to call the `gcdaikin` CLI to generate codes. Returns stdout or
    None if CLI not found or fails."""
    exe = shutil.which("gcdaikin")
    if not exe:
        print("`gcdaikin` CLI not found on PATH")
        return None

    # We don't know exact CLI flags (pyhvac may have changed). Ask the CLI
    # for help if the user didn't pass a raw `--cli-args` string.
    cli_args = [exe]
    if args.cli_args:
        cli_args.extend(args.cli_args.split())
    else:
        # Construct some sensible args; user may need to adapt this.
        cli_args.extend(["--model", args.model, "--mode", args.mode])
        if args.temp is not None:
            cli_args.extend(["--temp", str(args.temp)])
        if args.fan:
            cli_args.extend(["--fan", args.fan])
        # Request broadlink output when possible; many gc* utilities support -b/--b64
        cli_args.append("--b64")

    try:
        out = subprocess.check_output(cli_args, stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        print("gcdaikin failed:\n", e.output.decode("utf-8", errors="ignore"))
        return None
    except FileNotFoundError:
        print("gcdaikin not found when attempting to execute it")
        return None


def main():
    p = argparse.ArgumentParser(description="Generate Daikin codes with pyhvac (best-effort)")
    p.add_argument("--model", default="generic", help="Device model name (plugin-specific)")
    p.add_argument("--mode", default="cool", help="Operating mode: off, auto, cool, heat, dry, fan")
    p.add_argument("--temp", type=float, default=None, help="Target temperature (if applicable)")
    p.add_argument("--fan", default=None, help="Fan speed string (auto, low, medium, high, etc.)")
    p.add_argument("--format", default="broadlink", choices=("broadlink", "lirs", "frames"), help="Desired output format")
    p.add_argument("--cli-args", default=None, help="Raw extra args to pass to gcdaikin CLI if using fallback")
    args = p.parse_args()

    # 1) Try library approach
    print("Trying pyhvac library...")
    lib_out = try_pyhvac_generate(args.model, args.mode, args.temp, args.fan, args.format)
    if lib_out:
        print("Generated via pyhvac library:\n")
        print(lib_out)
        return

    # 2) Try CLI fallback
    print("Falling back to gcdaikin CLI...")
    cli_out = try_cli_gcdaikin(args)
    if cli_out:
        print("Generated via gcdaikin CLI:\n")
        print(cli_out)
        return

    print("Failed to generate code via pyhvac or gcdaikin. Please install pyhvac and check available plugins.")


if __name__ == "__main__":
    main()
