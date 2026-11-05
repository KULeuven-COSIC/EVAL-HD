#!/usr/bin/env python3

from pyosys import libyosys as ys
import argparse
import json
import tempfile

# Timing constraints for ABC in the timing analysis: the cell driving the inputs of the logic and the
# load on its outputs (in fF), as in OpenROAD-flow-scripts for NanGate45, the library of FreePDK45
# (flow/platforms/nangate45/config.mk: ABC_DRIVER_CELL = BUF_X1 and ABC_LOAD_IN_FF = 3.898, the
# input capacitance of BUF_X1, 0.974659 fF, multiplied by 4).
ABC_DRIVING_CELL = "BUF_X1"
ABC_LOAD = 3.898

# Tightest timing constraint (in picoseconds), which cannot be met: ABC then optimizes, buffers and
# sizes the gates with maximum effort, so the estimated delay is the shortest critical path it finds.
TIGHTEST_TARGET = 1

def report_modules(design, cell_library: str) -> None:
    with tempfile.NamedTemporaryFile("rt", suffix=".json") as f:
        ys.run_pass(f"tee -q -o {f.name} stat -json -liberty {cell_library}", design)
        modules = json.load(f)["modules"]

    def children(name: str) -> dict:
        return {c: n for c, n in modules[name]["num_cells_by_type"].items() if "\\" + c in modules or c in modules}

    def key(name: str) -> str:
        return name if name in modules else "\\" + name

    # the area of a module includes its submodules (Yosys >= 0.4x); subtract them for its own area
    # (a module without cells has no area in the report)
    area = {name: info.get("area", 0.0) for name, info in modules.items()}
    own = {}
    for name in modules:
        sub = sum(n * area[key(c)] for c, n in children(name).items())
        own[name] = area[name] - sub if area[name] >= sub - 1e-6 else area[name]

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

def synthesize(design, design_file: str, top_module: str, cell_library: str, flatten: bool) -> None:
    # read design
    ys.run_pass(f"read_verilog {design_file}", design)

    # elaborate design hierarchy
    ys.run_pass(f"hierarchy -check -top {top_module}", design)

    if flatten:
        # flatten the design
        ys.run_pass("flatten", design)

    # the high-level stuff
    ys.run_pass("proc; opt; fsm; opt; memory; opt", design)

    # mapping to internal cell library
    ys.run_pass("techmap; opt", design)

    # mapping flip-flops to cell library
    ys.run_pass(f"dfflibmap -liberty {cell_library}", design)

def run_analysis(report_timing: bool, keep_hierarchy: bool, modules: bool, design_file: str, top_module: str, cell_library: str) -> None:
    design = ys.Design()

    synthesize(design, design_file, top_module, cell_library, flatten=not keep_hierarchy)

    if report_timing:
        # the timing analysis maps the same synthesized design again
        ys.run_pass("design -save synthesized", design)

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

    if report_timing:
        # mapping logic to cell library with the tightest timing constraint: with -constr, the
        # default ABC script also buffers and sizes the gates and reports the delay ('stime')
        ys.run_pass("design -load synthesized", design)
        with tempfile.NamedTemporaryFile("wt", suffix=".constr") as constraints:
            # timing constraints: the cell driving the inputs and the load on the outputs
            constraints.write(f"set_driving_cell {ABC_DRIVING_CELL}\nset_load {ABC_LOAD}\n")
            constraints.flush()
            ys.run_pass(f"abc -liberty {cell_library} -constr {constraints.name} -D {TIGHTEST_TARGET}", design)

def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize a design for ASIC using Yosys.")
    parser.add_argument("design_file", type=str, help="Path to the Verilog design file.")
    parser.add_argument("--top-module", type=str, default="Core", help="Name of the top module (default: Core).")
    parser.add_argument("--cell-library", default="freepdk-45nm/stdcells.lib", help="Path to the cell library (default: FreePDK).")
    parser.add_argument("--report-timing", action="store_true", help="Also estimate the shortest critical path (mapping with the tightest timing constraint).")
    parser.add_argument("--keep-hierarchy", action="store_true", help="Do not flatten the design (needed to report the area of every module).")
    parser.add_argument("--report-modules", action="store_true", help="Report the area of every module.")
    args = parser.parse_args()

    run_analysis(args.report_timing, args.keep_hierarchy, args.report_modules, args.design_file, args.top_module, args.cell_library)

if __name__ == "__main__":
    main()
