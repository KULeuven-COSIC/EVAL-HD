#!/usr/bin/env python3

import argparse
import subprocess
import re
from typing import Optional


def bridge_command(design_file: str, top_module: str, cell_library: str) -> list:
    return [
        "./yosys-bridge.py",
        design_file,
        "--top-module", top_module,
        "--cell-library", cell_library
    ]


def parse_area(stdout: str, top_module: str) -> Optional[float]:
    # 'Chip area for module' (flattened design) or 'Chip area for top module' (hierarchical design)
    rs = re.findall(r"Chip area for (?:top )?module \'\\" + top_module + r"\': (\d+.\d+)", stdout)
    return float(rs[-1]) if rs else None


def print_modules(stdout: str) -> None:
    modules = [(int(rs.group(1)), rs.group(2), int(rs.group(3)), float(rs.group(4)), float(rs.group(5)))
               for rs in re.finditer(r"^MODULE (\d+) (\S+) instances=(\d+) own=(\d+.\d+) total=(\d+.\d+)$", stdout, re.MULTILINE)]
    if not modules:
        print("Failed to parse the module areas.")
        return

    design_area = modules[0][4]
    print(f"{'Module (hierarchy)':48s} {'Instances':>9s} {'Area incl. submodules':>21s} {'Share':>7s} {'Own area':>11s} {'Share':>7s}")
    for depth, name, instances, own, total in modules:
        print(f"{'  ' * depth + name:48s} {instances:9d} {total * instances:21.2f} {100 * total * instances / design_area:6.1f}% "
              f"{own * instances:11.2f} {100 * own * instances / design_area:6.1f}%")
    print("(areas in µm² over all instances of a module; the own areas add up to the design area)")


def run_bridge(command: list, logging: bool) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if logging:
        with open("eval_output.txt", 'at') as f:
            f.write(result.stdout)
    return result.stdout


def failed(measurement: str) -> None:
    print(f"Failed to parse {measurement} measurement.")
    print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
    print("Exiting!")
    exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find the area and the shortest critical path for a design with EVAL-HD.")
    parser.add_argument("design_file", type=str,
                        help="Path to the Verilog design file.")
    parser.add_argument("--top-module", type=str, default="Core",
                        help="Name of the top module (default: Core).")
    parser.add_argument("--cell-library", default="freepdk-45nm/stdcells.lib",
                        help="Path to the cell library (default: freepdk-45nm/stdcells.lib).")
    parser.add_argument("--logging", action="store_true",
                        help="Log the full Yosys output in eval_output.txt.")
    parser.add_argument("--report-timing", action="store_true",
                        help="Also report the shortest critical path, as estimated by ABC.")
    parser.add_argument("--report-modules", action="store_true",
                        help="Report the area of every module (synthesized without flattening).")
    args = parser.parse_args()

    if args.report_timing or args.report_modules:
        command = bridge_command(args.design_file, args.top_module, args.cell_library)
        if args.logging:
            open("eval_output.txt", 'wt').close()

        if args.report_modules:
            # module areas need the hierarchy: the design is synthesized without flattening it, and
            # this area is reported
            modules = run_bridge(command + ["--keep-hierarchy", "--report-modules"], args.logging)
            area = parse_area(modules, args.top_module)

        if args.report_timing:
            # the (flattened) design is mapped for its area, and again with the tightest timing
            # constraint, for which ABC estimates the delay
            timing = run_bridge(command + ["--report-timing"], args.logging)
            if not args.report_modules:
                area = parse_area(timing, args.top_module)
            delays = re.findall(r"Delay =\s*(\d+.\d+) ps", timing)
            if not delays:
                failed("timing")
            delay = float(delays[-1])

        if area is None:
            failed("area")
        print(f"Area = {area:.2f} µm² = {(area / 1000000):.4f} mm²")
        if args.report_timing:
            print(f"Estimated delay with the tightest timing constraint: {delay:.1f} ps = "
                  f"{delay / 1000:.3f} ns = {1 / (delay / 1000000):.2f} MHz")
        if args.report_modules:
            print_modules(modules)
    else:
        subprocess.run(bridge_command(args.design_file, args.top_module, args.cell_library), text=True)


if __name__ == "__main__":
    main()
