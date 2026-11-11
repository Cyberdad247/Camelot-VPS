# SPDX-License-Identifier: MIT

"""CLI entry for `python -m control_plane.runic_router --rune X --task Y`."""
import argparse
import json
import sys

from control_plane.runes.runic_router import detect_and_route, list_runes, route_rune


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m control_plane.runic_router",
        description="CAMELOT-OS Runic Dispatch — routes runes to knights",
    )
    sub = parser.add_subparsers(dest="cmd")

    # route: --rune X --task Y
    r = sub.add_parser("route", help="Route a rune to its knight")
    r.add_argument("--rune", required=True, help="Rune name (e.g. FORGE, //BOOT, Omega_SYNC)")
    r.add_argument("--task", default="", help="Task parameter passed to the rune handler")

    # detect: parse free-form text for rune prefix
    d = sub.add_parser("detect", help="Detect and route rune from free-form text")
    d.add_argument("text", nargs="+", help="Text to parse for rune prefix")

    # list: show all runes
    sub.add_parser("list", help="List all available runes")

    args = parser.parse_args()

    if args.cmd == "list":
        runes = list_runes()
        print("=== Runic Commands ===")
        for r in runes["runic_commands"]:
            print(f"  {r}")
        print("\n=== Omega Runes ===")
        for r in runes["omega_runes"]:
            print(f"  {r}")
        return

    if args.cmd == "route":
        rune = args.rune if args.rune.startswith("//") or args.rune.startswith("Omega_") else f"//{args.rune.upper()}"
        result = route_rune(rune, args.task)

    elif args.cmd == "detect":
        text = " ".join(args.text)
        result = detect_and_route(text)
        if result is None:
            print(json.dumps({"error": "No rune detected in input"}))
            sys.exit(1)

    else:
        # Default: treat first arg as free-form text containing a rune
        parser.print_help()
        sys.exit(0)

    print(json.dumps({
        "rune": result.rune,
        "knight": result.knight,
        "directive": result.directive,
        "mode": result.mode,
        "task_id": result.task_id,
        "queued": result.queued,
        "metadata": result.metadata,
    }, indent=2))


if __name__ == "__main__":
    main()
