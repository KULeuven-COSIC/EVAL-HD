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
                  [--report-timing] [--report-modules]
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
  --logging             Log the full Yosys output in eval_output.txt.
  --report-timing       Also report the shortest critical path, as estimated by ABC.
  --report-modules      Report the area of every module (synthesized without flattening).
```

For additional configuration, such as using SystemVerilog or multiple source files, it is recommended to modify the script directly.

The script synthesizes the target design into a (flattened) ASIC netlist and displays ASIC area numbers [\mu m^2].

Additionally, if the `--report-timing` flag is set, the critical path of the design is estimated.
The synthesized design is then mapped once more by ABC, with the tightest timing constraint, and the delay of the result is estimated by ABC (`stime`).

```shell
$ ./eval-hd.py examples/core-ami-static.v --report-timing
Area = 41286.39 µm² = 0.0413 mm²
Estimated delay with the tightest timing constraint: 2868.2 ps = 2.868 ns = 348.65 MHz
```

If the `--report-modules` flag is set, the area of every module is reported in the hierarchy of the design, with the number of instances, the area including the submodules and the own area of the module:

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

The module areas require the hierarchy of the design, so with this flag the design is synthesized without flattening it, and the reported area is the area of this hierarchical netlist.
Since logic is then not optimized across module boundaries, this total area can differ from the area without the flag (typically by a few percent), but the proportions of the modules are representative.

## :hourglass_flowing_sand: Version history

- `v0.4`: Fixes and functionality improvements
- `v0.3`: Refactored interface
- `v0.2`: Switch to `pyosys` and addition of the timing search
- `v0.1`: Initial release

## :book: Bibliography

If you use or build upon the code in this repository, please cite our paper using our [citation key](CITATION).
