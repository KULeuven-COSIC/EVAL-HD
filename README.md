# EVAL-HD

This repository contains an artifact for evaluating the cost of hardware implementations, using an open-source, ASIC-based toolchain.\
The artifact is described in our paper 'Hardware Cost Evaluation in Systems Security' ([DOI](https://doi.org/10.1145/3736731.3746155), [preprint](https://mici.hu/papers/demeulemeester25hardwarecost.pdf)).

## :file_folder: Contents

- [freepdk-45nm](https://github.com/mflowgen/freepdk-45nm): 45nm ASIC cell library
- [examples](examples/): [Proteus \& extensions](https://github.com/proteus-core/proteus) (HDL examples)

## :hammer: Installing EVAL-HD

### Pre-requisites

- Python + pip

### Cloning the Repository

To ensure all required libraries (git sub-modules) are included and downloaded, use:

```shell
git clone --recurse-submodules https://github.com/KULeuven-COSIC/eval-hd.git
```

Then install `pyosys` from pip:

```shell
pip install -r requirements.txt
```

## :bar_chart: Using EVAL-HD

Most of the functionality can be configured using the parameters of the `eval-hd.py` script:

```shell
$ ./eval-hd.py --help
usage: eval-hd.py [-h] [--top-module TOP_MODULE] [--cell-library CELL_LIBRARY] [--logging]
                  [--maximum-target MAXIMUM_TARGET] [--report-modules]
                  design_file

Find the area and the shortest critical path for a design with EVAL-HD.

positional arguments:
  design_file           Path to the Verilog design file.

options:
  -h, --help            show this help message and exit
  --top-module TOP_MODULE
                        Name of the top module (default: Core).
  --cell-library CELL_LIBRARY
                        Path to the cell library (default: freepdk-45nm/stdcells.lib).
  --logging             Log full Yosys output in text files.
  --maximum-target MAXIMUM_TARGET
                        Maximum timing constraint (in picoseconds).
  --report-modules      Report the area of every module (in the timing search: at the shortest met
                        target).

$ ./eval-hd.py examples/core-ami-static.v --maximum-target 11000
Starting timing search up to 11000 ps...
Timing failed (2000 ps, estimated delay 2868.2 ps)
Area = 42960.33 µm² = 0.0430 mm²
Timing met: 3000 ps = 3.0 ns = 333.33 MHz (estimated delay 2998.7 ps)
Timing failed (2100 ps, estimated delay 2868.2 ps)
[...]
Timing failed (2868 ps, estimated delay 2868.2 ps)
Area = 42991.19 µm² = 0.0430 mm²
Timing met: 2869 ps = 2.869 ns = 348.55 MHz (estimated delay 2868.2 ps)
```

For additional configuration, such as using SystemVerilog or multiple source files, it is recommended to modify the script directly.

The script synthesizes the target design into a (flattened) ASIC netlist and displays ASIC area numbers [\mu m^2].

Additionally, if the `--maximum-target` flag is set, the critical path of the design can be determined.
For every timing constraint, the delay of the (flattened) netlist is estimated by ABC (`stime`) and printed.
If the estimated delay exceeds the timing constraint, the timing fails (see the example above).
The script will then automatically relax the constraint and repeat until the constraint is met.

If the `--report-modules` flag is set, the area of every module is reported in the hierarchy of the design, with the number of instances, the area including the submodules and the own area of the module (together with `--maximum-target`, at the shortest met target):

```shell
$ ./eval-hd.py examples/core-ami-static.v --report-modules
Area = 43717.37 µm² = 0.0437 mm²
Module (hierarchy)                               Instances Area incl. submodules   Share    Own area   Share
Core                                                     1              43717.37  100.0%      426.13    1.0%
  Pipeline                                               1              40390.50   92.4%     2269.51    5.2%
    RegisterFile                                         1               9271.70   21.2%     9271.70   21.2%
    Stage_IF                                             1               9253.87   21.2%     1086.61    2.5%
      StreamFifoLowLatency_3                             1               5251.11   12.0%        0.00    0.0%
        StreamFifo_2                                     1               5251.11   12.0%     5251.11   12.0%
[...]
(areas in µm² over all instances of a module; the own areas add up to the design area)
```

The module areas require the hierarchy of the design, so with this flag the design is synthesized without flattening it (after the timing search, in an additional synthesis at the shortest met target), and the reported area is the area of this hierarchical netlist.
Since logic is then not optimized across module boundaries, this total area can differ from the area without the flag (typically by a few percent), but the proportions of the modules are representative.

## :hourglass_flowing_sand: Version history

- `v0.4`: Fixes and functionality improvements
- `v0.3`: Refactored interface
- `v0.2`: Switch to `pyosys` and addition of the timing search
- `v0.1`: Initial release

## :book: Bibliography

If you use or build upon the code in this repository, please cite our paper using our [citation key](CITATION).
