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


def timing_analysis(design_file: str, top_module: str, cell_library: str, logging: bool) -> Optional[int]:
    print("Starting timing analysis...")

    # one Yosys process: the design is synthesized once and mapped for every target, which is
    # reported on stderr while the analysis runs
    log = open("eval_output.txt", 'wt') if logging else subprocess.DEVNULL
    process = subprocess.Popen(bridge_command(design_file, top_module, cell_library) + [
        "--timing-analysis"
    ], stdout=log, stderr=subprocess.PIPE, text=True)

    best_target = None
    any_failed = False
    failed_delay = None
    errors = []
    for line in process.stderr:
        line = line.strip()
        if bs := re.match(r"BEST delay=(\d+.\d+)$", line):
            print(f"Estimated delay with the tightest timing constraint: {float(bs.group(1)):.1f} ps")
        elif ts := re.match(r"TRY target=(\d+)$", line):
            # a failed target is reported together with the next one that is tried
            if failed_delay is None:
                print(f"Trying {ts.group(1)} ps...")
            else:
                print(f"Timing failed (estimated delay {failed_delay:.1f} ps), trying {ts.group(1)} ps...")
                failed_delay = None
        elif rs := re.match(r"TIMING target=(\d+) met=(\d) delay=(\d+.\d+) area=(\S+)$", line):
            target, met, delay = int(rs.group(1)), rs.group(2) == "1", float(rs.group(3))
            if not met:
                any_failed = True
                failed_delay = delay
            elif rs.group(4) == "-":
                print("Failed to parse area measurement.")
                print("This likely indicates an error, it is recommended to run the script with --logging and examine the output.")
                print("Exiting!")
                exit(1)
            else:
                area = float(rs.group(4))
                best_target = target
                print(f"Area = {area:.2f} µm² = {(area / 1000000):.4f} mm²")
                print(f"Timing met: {target} ps = {target / 1000} ns = {1 / (target / 1000000):.2f} MHz")
        else:
            errors.append(line + "\n")

    if failed_delay is not None:
        print(f"Timing failed (estimated delay {failed_delay:.1f} ps)")

    if process.wait() != 0 or best_target is None and not any_failed:
        print("".join(errors[-20:]), end="")
        print("The timing analysis failed, it is recommended to run the script with --logging and examine the output.")
        print("Exiting!")
        exit(1)

    if best_target is None:
        print("No target met at the estimated delay.")

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
                        help="Log the full Yosys output in eval_output.txt.")
    parser.add_argument("--report-timing", action="store_true",
                        help="Report the shortest critical path, as estimated by ABC.")
    parser.add_argument("--report-modules", action="store_true",
                        help="Report the area of every module (with --report-timing: for the met timing constraint).")
    args = parser.parse_args()

    if args.report_timing:
        best_target = timing_analysis(args.design_file, args.top_module, args.cell_library, args.logging)
        if args.report_modules and best_target is not None:
            # module areas need the hierarchy, which the timing analysis flattens: synthesize again at
            # the met target without flattening, and report that area
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
