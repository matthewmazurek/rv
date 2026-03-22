# r-init

Lightweight shell tool to scaffold a ready-to-go R project — similar to `uv init` or `bun init`, but for R.

Creates a directory with sensible defaults: git, renv, config, utility helpers, and a standard layout.

## Installation

Clone the repo and optionally symlink the script onto your PATH:

```bash
git clone https://github.com/matthewmazurek/r-init.git ~/.r-init
ln -s ~/.r-init/init.sh /usr/local/bin/r-init
```

Or run directly:

```bash
bash /path/to/r-init/init.sh my_project
```

## Usage

```
r-init <project_name> [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--no-git` | git **on** | Skip git initialization |
| `--no-renv` | renv **on** | Skip renv bootstrap in setup script |
| `--rproj` | off | Create an RStudio `.Rproj` file |
| `--slurm` | off | Include a SLURM job template |
| `--force` | off | Allow creation in a non-empty directory |
| `-h, --help` | | Show help |

### Examples

```bash
# Defaults: git + renv
r-init my_analysis

# Kitchen sink
r-init my_analysis --rproj --slurm

# Minimal (no git, no renv)
r-init my_analysis --no-git --no-renv
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
With `--rproj`: adds `<project_name>.Rproj`.

## Customization

Templates live in the `templates/` directory next to `init.sh`. Edit them directly to change what gets generated:

- **Verbatim files** are copied as-is (e.g. `templates/R/utils.R`).
- **`.tmpl` files** undergo `{{PROJECT_NAME}}` substitution before copying (e.g. `templates/README.md.tmpl`).
- **`setup_env_renv.snippet`** is injected into `setup_env.R` when renv is enabled.

## Requirements

- Bash 4+
- `sed` (BSD or GNU)
- `git` (optional, for `--git`)
