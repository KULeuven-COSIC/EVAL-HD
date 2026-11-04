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


def run_with_timing(design_file: str, top_module: str, target: int, cell_library: str, logging: bool) -> bool:
    timing_success = True

    result = subprocess.run(bridge_command(design_file, top_module, cell_library) + [
        "--report-timing",
        "--timing-target", str(target)
    ], capture_output=True, text=True)

    if logging:
        with open(f"eval_output_{target}.txt", 'wt') as f:
            f.write(result.stdout)

    # the delay of the mapped and sized design, as estimated by ABC (stime)
    drs = re.findall(r"Delay =\s*(\d+.\d+) ps", result.stdout)
    if not drs:
        print("Failed to parse timing measurement.")
        print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
        print("Exiting!")
        exit(1)
    delay = float(drs[-1])
    if delay > target:
        print(f"Timing failed ({target} ps, estimated delay {delay:.1f} ps)")
        timing_success = False
    else:
        area = parse_area(result.stdout, top_module)
        if area is not None:
            print(f"Area = {area:.2f} µm² = {(area / 1000000):.4f} mm²")
            print(
                f"Timing met: {target} ps = {target / 1000} ns = {1 / (target / 1000000):.2f} MHz (estimated delay {delay:.1f} ps)")
        else:
            print("Failed to parse area measurement.")
            print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
            print("Exiting!")
            exit(1)

    return timing_success


def naive_search(design_file: str, top_module: str, maximum_target: int, cell_library: str, logging: bool) -> Optional[int]:
    successful_target = maximum_target
    success = False
    any_failed = False
    best_target = None

    print(f"Starting timing search up to {maximum_target} ps...")

    for step in [1000, 100, 10, 1]:
        for target in range(successful_target - 9 * step, successful_target, step):
            success = run_with_timing(
                design_file, top_module, target, cell_library, logging)
            if success:
                successful_target = target
                best_target = target
                break
            else:
                any_failed = True

    if not any_failed:
        print("No timing measurement failed. It is recommended to configure a lower maximum target to find the shortest critical path.")

    return best_target

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
                        help="Log full Yosys output in text files.")
    parser.add_argument("--maximum-target", type=int,
                        help="Maximum timing constraint (in picoseconds).")
    parser.add_argument("--report-modules", action="store_true",
                        help="Report the area of every module (in the timing search: at the shortest met target).")
    args = parser.parse_args()

    if args.maximum_target is not None:
        best_target = naive_search(args.design_file, args.top_module, args.maximum_target, args.cell_library, args.logging)
        if args.report_modules and best_target is not None:
            # module areas need the hierarchy, which the timing search flattens: synthesize again at
            # the shortest met target without flattening, and report that area
            result = subprocess.run(bridge_command(args.design_file, args.top_module, args.cell_library) + [
                "--report-timing", "--keep-hierarchy", "--report-modules",
                "--timing-target", str(best_target)
            ], capture_output=True, text=True)
            area = parse_area(result.stdout, args.top_module)
            if area is None:
                print("Failed to parse area measurement.")
                print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
                print("Exiting!")
                exit(1)
            print(f"Area at {best_target} ps with module hierarchy = {area:.2f} µm² = {(area / 1000000):.4f} mm²")
            print_modules(result.stdout)
    elif args.report_modules:
        result = subprocess.run(bridge_command(args.design_file, args.top_module, args.cell_library) + [
            "--keep-hierarchy", "--report-modules"
        ], capture_output=True, text=True)
        if args.logging:
            with open("eval_output.txt", 'wt') as f:
                f.write(result.stdout)
        area = parse_area(result.stdout, args.top_module)
        if area is None:
            print("Failed to parse area measurement.")
            print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
            print("Exiting!")
            exit(1)
        print(f"Area = {area:.2f} µm² = {(area / 1000000):.4f} mm²")
        print_modules(result.stdout)
    else:
        subprocess.run(bridge_command(args.design_file, args.top_module, args.cell_library), text=True)


if __name__ == "__main__":
    main()
