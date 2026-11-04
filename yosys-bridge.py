#!/usr/bin/env python3

from pyosys import libyosys as ys
import argparse
import json
import math
import re
import sys
import tempfile
from typing import Optional

# Timing constraints for ABC in the timing analysis: the cell driving the inputs of the logic and the
# load on its outputs (in fF), as in OpenROAD-flow-scripts for NanGate45, the library of FreePDK45
# (flow/platforms/nangate45/config.mk: ABC_DRIVER_CELL = BUF_X1 and ABC_LOAD_IN_FF = 3.898, the
# input capacitance of BUF_X1, 0.974659 fF, multiplied by 4).
ABC_DRIVING_CELL = "BUF_X1"
ABC_LOAD = 3.898

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

def logged(design, command: str) -> str:
    # run a command and return its log output
    with tempfile.NamedTemporaryFile("rt", suffix=".log") as f:
        ys.run_pass(f"tee -o {f.name} {command}", design)
        return f.read()

def map_logic(design, cell_library: str, timing_target: Optional[int]) -> str:
    if timing_target is None:
        # mapping logic to cell library
        return logged(design, f"abc -liberty {cell_library}")

    # mapping logic to cell library with timing constraint: with -constr, the default ABC script
    # also buffers and sizes the gates for the target and reports the delay ('stime')
    with tempfile.NamedTemporaryFile("wt", suffix=".constr") as constraints:
        # timing constraints: the cell driving the inputs and the load on the outputs
        constraints.write(f"set_driving_cell {ABC_DRIVING_CELL}\nset_load {ABC_LOAD}\n")
        constraints.flush()
        return logged(design, f"abc -liberty {cell_library} -constr {constraints.name} -D {timing_target}")

def finish(design, cell_library: str, write_netlist: bool = True) -> Optional[float]:
    # cleanup
    ys.run_pass("clean", design)

    # write synthesized design
    if write_netlist:
        ys.run_pass("write_verilog result.v", design)

    # get ASIC gate count and area numbers
    stat = logged(design, f"stat -liberty {cell_library}")
    rs = re.findall(r"Chip area for (?:top )?module '.*': (\d+.\d+)", stat)
    return float(rs[-1]) if rs else None

def evaluate(design, cell_library: str, target: int, probe: bool = False) -> tuple:
    # map the synthesized design for one target: met, estimated delay and area (a probe only reports
    # the delay); the steps are reported on stderr, which is not buffered and not mixed with the
    # Yosys output
    if not probe:
        print(f"TRY target={target}", file=sys.stderr, flush=True)
    ys.run_pass("design -load synthesized", design)
    abc = map_logic(design, cell_library, target)
    delays = re.findall(r"Delay =\s*(\d+.\d+) ps", abc)
    if not delays:
        sys.exit("Failed to parse the delay reported by ABC.")
    delay = float(delays[-1])
    met = delay <= target
    # the netlist of the met target is kept in result.v
    area = finish(design, cell_library, write_netlist=met)

    if probe:
        print(f"BEST delay={delay:.2f}", file=sys.stderr, flush=True)
    else:
        print(f"TIMING target={target} met={int(met)} delay={delay:.2f} "
              f"area={'-' if area is None else f'{area:.3f}'}", file=sys.stderr, flush=True)
    return met, delay

def timing_analysis(evaluate_target) -> None:
    # the delay with the tightest target (1 ps), for which the gates are sized with maximum effort
    _, delay = evaluate_target(1, probe=True)

    # the design for a target of this delay (rounded up), for its area and to check that the target
    # is met; if not, again for the delay reached there (with a longer target, the gates are sized
    # with less effort, so the delay can increase), at most 10 times
    for _ in range(10):
        met, delay = evaluate_target(math.ceil(delay))
        if met:
            return

def run_analysis(report_timing: bool, keep_hierarchy: bool, modules: bool, design_file: str, top_module: str, timing_target: int, timing_analysis_mode: bool, cell_library: str) -> None:
    design = ys.Design()

    if timing_analysis_mode:
        # timing analysis: the design is synthesized once, only the mapping depends on the target
        synthesize(design, design_file, top_module, cell_library, flatten=True)
        ys.run_pass("design -save synthesized", design)
        timing_analysis(lambda target, probe=False: evaluate(design, cell_library, target, probe))
        return

    synthesize(design, design_file, top_module, cell_library, flatten=not keep_hierarchy)
    map_logic(design, cell_library, timing_target if report_timing else None)
    finish(design, cell_library)

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
    parser.add_argument("--timing-analysis", action="store_true", help="Analyze the timing: the delay with the tightest timing constraint, and the design at a constraint of that delay; reported per step on stderr.")
    parser.add_argument("--keep-hierarchy", action="store_true", help="Do not flatten the design (needed to report the area of every module).")
    parser.add_argument("--report-modules", action="store_true", help="Report the area of every module.")
    args = parser.parse_args()

    run_analysis(args.report_timing, args.keep_hierarchy, args.report_modules, args.design_file, args.top_module, args.timing_target, args.timing_analysis, args.cell_library)

if __name__ == "__main__":
    main()
