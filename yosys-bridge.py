#!/usr/bin/env python3

from pyosys import libyosys as ys
import argparse
import json
import tempfile

def report_modules(design, cell_library: str) -> None:
    with tempfile.NamedTemporaryFile("rt", suffix=".json") as f:
        ys.run_pass(f"tee -q -o {f.name} stat -json -liberty {cell_library}", design)
        modules = json.load(f)["modules"]

    def children(name: str) -> dict:
        return {c: n for c, n in modules[name]["num_cells_by_type"].items() if "\\" + c in modules or c in modules}

    def key(name: str) -> str:
        return name if name in modules else "\\" + name

    # the area of a module includes its submodules (Yosys >= 0.4x); subtract them for its own area
    own = {}
    for name, info in modules.items():
        sub = sum(n * modules[key(c)]["area"] for c, n in children(name).items())
        own[name] = info["area"] - sub if info["area"] >= sub - 1e-6 else info["area"]

    total = {}
    def total_area(name: str) -> float:
        if name not in total:
            total[name] = own[name] + sum(n * total_area(key(c)) for c, n in children(name).items())
        return total[name]

    # number of instances of every module in the design
    top = design.top_module().name.str()
    count = {}
    def count_instances(name: str, n: int) -> None:
        count[name] = count.get(name, 0) + n
        for c, k in children(name).items():
            count_instances(key(c), n * k)
    count_instances(top, 1)

    # hierarchy depth-first from the top module, largest submodules first, every module once
    seen = set()
    def walk(name: str, depth: int) -> None:
        seen.add(name)
        # log through Yosys, so the line is not interleaved with the Yosys output
        ys.log(f"MODULE {depth} {name[1:] if name.startswith(chr(92)) else name} instances={count[name]} "
               f"own={own[name]:.3f} total={total_area(name):.3f}\n")
        for c, n in sorted(children(name).items(), key=lambda cn: -cn[1] * total_area(key(cn[0]))):
            if key(c) not in seen:
                walk(key(c), depth + 1)
    walk(top, 0)

def run_analysis(report_timing: bool, keep_hierarchy: bool, modules: bool, design_file: str, top_module: str, timing_target: int, cell_library: str) -> None:
    design = ys.Design()

    # read design
    ys.run_pass(f"read_verilog {design_file}", design)

    # elaborate design hierarchy
    ys.run_pass(f"hierarchy -check -top {top_module}", design)

    if not keep_hierarchy:
        # flatten the design
        ys.run_pass("flatten", design)

    # the high-level stuff
    ys.run_pass("proc; opt; fsm; opt; memory; opt", design)

    # mapping to internal cell library
    ys.run_pass("techmap; opt", design)

    # mapping flip-flops to cell library
    ys.run_pass(f"dfflibmap -liberty {cell_library}", design)

    if report_timing:
        # mapping logic to cell library with timing constraint
        ys.run_pass(f"abc -liberty {cell_library} -fast -D {timing_target}", design)
    else:
        # mapping logic to cell library
        ys.run_pass(f"abc -liberty {cell_library}", design)

    # cleanup
    ys.run_pass("clean", design)

    # write synthesized design
    ys.run_pass("write_verilog result.v", design)

    # get ASIC gate count and area numbers
    ys.run_pass(f"stat -liberty {cell_library}", design)

    if modules:
        # get the area of every module
        report_modules(design, cell_library)

def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize a design for ASIC using Yosys.")
    parser.add_argument("design_file", type=str, help="Path to the Verilog design file.")
    parser.add_argument("--top-module", type=str, default="Core", help="Name of the top module (default: Core).")
    parser.add_argument("--cell-library", default="freepdk-45nm/stdcells.lib", help="Path to the cell library (default: FreePDK).")
    parser.add_argument("--report-timing", action="store_true", help="Enable timing analysis during synthesis.")
    parser.add_argument("--timing-target", type=int, default=2500, help="Target timing constraint (in picoseconds, default: 2500).")
    parser.add_argument("--keep-hierarchy", action="store_true", help="Do not flatten the design (needed to report the area of every module).")
    parser.add_argument("--report-modules", action="store_true", help="Report the area of every module.")
    args = parser.parse_args()

    run_analysis(args.report_timing, args.keep_hierarchy, args.report_modules, args.design_file, args.top_module, args.timing_target, args.cell_library)

if __name__ == "__main__":
    main()
