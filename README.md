# rv

Lightweight R project manager — like [`uv`](https://github.com/astral-sh/uv) for Python, but for R.

`rv` gives R the same workflow that `uv` brought to Python: a single CLI that scaffolds opinionated project structures, manages dependencies through a human-readable `rproject.toml` manifest, and handles the full lifecycle — from adding packages (`rv add dplyr`) and running scripts (`rv run`) to generating SLURM batch jobs, Dockerfiles, and CI pipelines — while using [renv](https://rstudio.github.io/renv/) under the hood for library isolation and [pak](https://pak.r-lib.org/) for fast parallel installs, so you never have to drop into an R console just to set up or reproduce a project.

## Install

```bash
uv tool install git+https://github.com/matthewmazurek/rv.git
```

<details>
<summary>Alternative: from source</summary>

```bash
git clone https://github.com/matthewmazurek/rv.git ~/.rv
chmod +x ~/.rv/rv
ln -s ~/.rv/rv /usr/local/bin/rv
```
</details>

## Quick start

```bash
rv init my_analysis           # scaffold a new project
cd my_analysis
rv add dplyr ggplot2          # add packages
rv run                        # run the default script
```

## Commands

| Command | Description |
|---------|-------------|
| `rv init <name>` | Create a new R project |
| `rv add <pkg>...` | Add packages |
| `rv rm <pkg>...` | Remove packages |
| `rv list` | List declared packages |
| `rv update [pkg]...` | Update packages to latest |
| `rv sync` | Install all listed packages |
| `rv run [script]` | Run an R script |
| `rv clean` | Remove generated outputs |

### `rv init`

```bash
rv init my_analysis                   # new directory
rv init .                             # scaffold in current directory
rv init my_analysis --rproj --slurm   # with RStudio + SLURM support
rv init my_analysis --docker --ci     # with Dockerfile + GitHub Actions
rv init my_analysis --apptainer       # with Apptainer definition (HPC)
rv init my_analysis --no-renv         # skip renv
```

Flags: `--no-git`, `--no-renv`, `--rproj`, `--slurm`, `--docker`, `--apptainer`, `--ci`, `--force`, `--no-sync`

### `rv add` / `rv rm`

```bash
rv add dplyr ggplot2 data.table
rv add Seurat==4.4.0              # pin a version
rv add SingleCellExperiment --bioc
rv rm dplyr
```

Packages are managed in `rproject.toml` and installed via [pak](https://pak.r-lib.org/). On Linux (e.g. HPC clusters), `rv` automatically configures [Posit Public Package Manager](https://packagemanager.posit.co/) so packages install as pre-built binaries instead of compiling from source.

### `rv update`

```bash
rv update              # update all to latest
rv update dplyr tidyr  # update specific packages
```

### `rv run`

```bash
rv run                                          # default script
rv run preprocess                               # named alias
rv run scripts/custom.R -- --input data.csv     # pass extra flags to R script
```

Script aliases are defined in `rproject.toml`:

```toml
[scripts]
default = "scripts/run_analysis.R"
preprocess = "scripts/preprocess.R"
```

Flags after `--` are passed to the R script as `--key value` pairs. Inside R, `config/analysis.yaml` provides defaults and CLI flags override any key:

```r
source("R/init.R")
# cfg$output  — from YAML default, unless --output was passed
# cfg$input   — NULL unless --input was passed (or set in YAML)
# cfg$seed    — NULL unless added to YAML (or passed via CLI)
```

### `rv clean`

```bash
rv clean         # clear results/ and logs/
rv clean --renv  # also remove renv library cache
```

## Project layout

```
my_analysis/
├── rproject.toml              # project manifest
├── config/
│   └── analysis.yaml    # defaults (output, etc.) — CLI overrides any key
├── R/
│   ├── init.R           # bootstrap (renv, config + CLI merge)
│   └── utils.R          # shared helpers
├── scripts/
│   └── run_analysis.R
├── data/
├── results/
├── logs/
├── tests/
└── docs/
```

The project manifest (`rproject.toml`) declares packages and script aliases:

```toml
renv = true
packages = ["yaml", "dplyr", "Seurat@4.4.0"]

[scripts]
default = "scripts/run_analysis.R"
```

With `--slurm`: adds `scripts/slurm_analysis.R` and `slurm/run_job.sh` (array jobs, GPU, email directives).
With `--rproj`: adds `<name>.Rproj`.
With `--docker`: adds `Dockerfile`.
With `--apptainer`: adds `<name>.def`.
With `--ci`: adds `.github/workflows/r-check.yml`.

## Containers

Scaffold a `Dockerfile` or Apptainer definition at init time, based on [rocker/r-ver](https://rocker-project.org/):

```bash
rv init my_analysis --docker          # adds Dockerfile
rv init my_analysis --apptainer       # adds my_analysis.def
```

Then build and run:

```bash
# Docker
docker build -t my_analysis .
docker run my_analysis

# Apptainer (HPC)
apptainer build my_analysis.sif my_analysis.def
apptainer run my_analysis.sif
```

Both install `rv`, sync packages from `rproject.toml`, and run the default script alias via `rv run`.

## CI

Scaffold a GitHub Actions workflow at init time:

```bash
rv init my_analysis --ci              # adds .github/workflows/r-check.yml
```

Includes R setup via `r-lib/actions`, renv caching, and a smoke-test run of the analysis.

## Shell completions

```bash
source ~/.rv/completions/rv.bash   # bash
source ~/.rv/completions/rv.zsh    # zsh
source ~/.rv/completions/rv.fish   # fish
```

## Requirements

- Python 3.11+
- R / Rscript
- git (optional)
