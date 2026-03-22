# rv

Lightweight R project manager — similar to `uv` for Python, but for R.

Scaffolds a project with sensible defaults (git, renv, config, helpers) and manages packages from the command line.

## Installation

```bash
git clone https://github.com/matthewmazurek/rv.git ~/.rv
chmod +x ~/.rv/rv
ln -s ~/.rv/rv /usr/local/bin/rv
```

## Usage

```
rv <command> [args...]
```

### Commands

| Command | Description |
|---------|-------------|
| `rv init <name>` | Create a new R project |
| `rv add <pkg>...` | Add packages to the project |
| `rv rm <pkg>...` | Remove packages from the project |
| `rv sync` | Install all listed packages |
| `rv run [script]` | Run an R script |

### `rv init`

```
rv init <name> [--no-git] [--no-renv] [--rproj] [--slurm] [--force] [--no-sync]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--no-git` | git **on** | Skip git initialization |
| `--no-renv` | renv **on** | Skip renv bootstrap |
| `--rproj` | off | Create an RStudio `.Rproj` file |
| `--slurm` | off | Include a SLURM job template |
| `--force` | off | Allow creation in a non-empty directory |
| `--no-sync` | sync **on** | Skip running `setup_env.R` after init |

```bash
rv init my_analysis
rv init my_analysis --rproj --slurm
rv init my_analysis --no-renv
```

### `rv add` / `rv rm`

```bash
rv add dplyr ggplot2 data.table
rv add Seurat==4.4.0              # pin to a specific version
rv add SingleCellExperiment --bioc
rv rm dplyr
```

`add` appends packages to `scripts/setup_env.R`, installs them via [`pak`](https://pak.r-lib.org/) (prefers binaries), and snapshots renv.
`rm` removes packages from the list and snapshots renv.

Version pins use `==` syntax (e.g. `Seurat==4.4.0`). Pinned packages are stored as `"pkg@version"` in `setup_env.R` and installed with `pak::pkg_install("pkg@version")`, which prefers pre-built binaries from Posit Package Manager over compiling from source.

### `rv sync`

```bash
rv sync
```

Runs `scripts/setup_env.R` to install all listed packages. Useful after cloning an existing project.

### `rv run`

```bash
rv run                           # runs scripts/run_analysis.R
rv run scripts/my_script.R       # runs a specific script
rv run scripts/my_script.R --input data/raw.csv
```

## Generated layout

```
my_analysis/
├── .gitignore
├── .Rprofile
├── README.md
├── config/
│   └── analysis.yaml
├── R/
│   └── utils.R
├── scripts/
│   ├── setup_env.R
│   └── run_analysis.R
├── data/
├── results/
├── logs/
├── tests/
└── docs/
```

With `--slurm`: adds `slurm/run_job.sh`.
With `--rproj`: adds `<name>.Rproj`.

## Customization

Templates live in `templates/` next to `rv.py`. Edit them to change what gets generated:

- **Verbatim files** are copied as-is (e.g. `templates/R/utils.R`).
- **`.tmpl` files** undergo `{{PROJECT_NAME}}` substitution (e.g. `templates/README.md.tmpl`).
- **`setup_env_renv.snippet`** is injected into `setup_env.R` when renv is enabled.

## Requirements

- Python 3.10+
- `git` (optional, for project init)
- R / `Rscript` (for `add`, `sync`, `run`)
