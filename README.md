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
usage: eval-hd.py [-h] [--top-module TOP_MODULE] [--cell-library CELL_LIBRARY] [--maximum-target MAXIMUM_TARGET] design_file

Find the area and the shortest critical path for a design with EVAL-HD.

positional arguments:
  design_file           Path to the Verilog design file.

options:
  -h, --help            show this help message and exit
  --top-module TOP_MODULE
                        Name of the top module (default: Core).
  --cell-library CELL_LIBRARY
                        Path to the cell library (default: freepdk-45nm/stdcells.lib).
  --maximum-target MAXIMUM_TARGET
                        Maximum timing constraint (in picoseconds).

$ ./eval-hd.py examples/core-ami-static.v --maximum-target 11000
Starting timing search up to 11000 ps...
Timing met: 2000 ps = 2.0 ns = 500.00 MHz
Area = 50168.93 µm² = 0.0502 mm²
Timing failed (1100 ps)
[...]
Timing failed (1992 ps)
Timing met: 1993 ps = 1.993 ns = 501.76 MHz
Area = 50210.16 µm² = 0.0502 mm²
```

For additional configuration, such as using SystemVerilog or multiple source files, it is recommended to modify the script directly.

The script synthesizes the target design into an ASIC netlist and displays ASIC area numbers [\mu m^2].

Additionally, if the `--maximum-target` flag is set, the critical path of the design can be determined.
If the (flattened) netlist does not meet the timing constraint, a warning will appear in the log messages (Step 13.1.1. Executing ABC.):

```shell
ABC: Cannot meet the target required times (X picoseconds). Continue anyway.
```

The script will then automatically relax the constraint and repeat until the constraint is met.

## :hourglass_flowing_sand: Version history

- `v0.4`: Fixes and functionality improvements
- `v0.3`: Refactored interface
- `v0.2`: Switch to `pyosys` and addition of the timing search
- `v0.1`: Initial release

## :book: Bibliography

If you use or build upon the code in this repository, please cite our paper using our [citation key](CITATION).
