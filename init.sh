#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  init_r_project.sh <project_name> [options]

Options:
  --git         Initialize a git repository
  --renv        Add renv bootstrap to setup script
  --rproj       Create an RStudio .Rproj file
  --force       Allow creation in a non-empty directory
  -h, --help    Show this help message

Examples:
  init_r_project.sh my_analysis
  init_r_project.sh my_analysis --git --renv --rproj
EOF
}

PROJECT_NAME=""
INIT_GIT=0
INIT_RENV=0
INIT_RPROJ=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --git)
      INIT_GIT=1
      shift
      ;;
    --renv)
      INIT_RENV=1
      shift
      ;;
    --rproj)
      INIT_RPROJ=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "$PROJECT_NAME" ]]; then
        PROJECT_NAME="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Error: project_name is required." >&2
  usage
  exit 1
fi

PROJECT_DIR="$PROJECT_NAME"

if [[ -e "$PROJECT_DIR" ]]; then
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "Error: $PROJECT_DIR exists and is not a directory." >&2
    exit 1
  fi

  if [[ "$FORCE" -ne 1 ]] && [[ -n "$(find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
    echo "Error: $PROJECT_DIR already exists and is not empty. Use --force to continue." >&2
    exit 1
  fi
fi

mkdir -p "$PROJECT_DIR"/{R,scripts,slurm,config,data,results,logs,docs}

cat > "$PROJECT_DIR/.gitignore" <<'EOF'
.Rhistory
.RData
.Ruserdata
.Rproj.user
.DS_Store

renv/library/
renv/python/
renv/staging/

results/
logs/*.out
logs/*.err
EOF

cat > "$PROJECT_DIR/.Rprofile" <<'EOF'
options(
  repos = c(CRAN = "https://cloud.r-project.org"),
  Ncpus = max(1L, parallel::detectCores(logical = FALSE) - 1L)
)

if (file.exists("renv/activate.R")) {
  source("renv/activate.R")
}
EOF

cat > "$PROJECT_DIR/README.md" <<EOF
# ${PROJECT_NAME}

General-purpose R project template.

## Layout

\`\`\`
${PROJECT_NAME}/
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
├── slurm/
│   └── run_job.sh
├── data/
├── results/
├── logs/
└── docs/
\`\`\`

## Quick start

### Interactive
Open the project in RStudio and run:

\`\`\`r
source("scripts/setup_env.R")
source("scripts/run_analysis.R")
\`\`\`

### Command line
\`\`\`bash
Rscript scripts/run_analysis.R
\`\`\`

### SLURM
Edit \`slurm/run_job.sh\`, then submit:

\`\`\`bash
sbatch slurm/run_job.sh
\`\`\`

## Notes

- Add project-specific package installs to \`scripts/setup_env.R\`
- Put reusable helpers in \`R/\`
- Keep raw input data in \`data/\`
- Write outputs to \`results/\`
EOF

cat > "$PROJECT_DIR/config/analysis.yaml" <<'EOF'
project_name: "replace_me"
seed: 123
future_workers: 1
EOF

cat > "$PROJECT_DIR/R/utils.R" <<'EOF'
suppressPackageStartupMessages({
  library(yaml)
})

`%||%` <- function(x, y) if (is.null(x)) y else x

get_project_root <- function() {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

load_config <- function(path = "config/analysis.yaml") {
  if (!file.exists(path)) {
    stop("Config file not found: ", path)
  }
  yaml::read_yaml(path)
}

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)

  out <- list(
    input = NULL,
    output = NULL,
    config = "config/analysis.yaml"
  )

  if (length(args) == 0) {
    return(out)
  }

  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]

    if (key %in% c("--input", "--output", "--config")) {
      if (i == length(args)) {
        stop("Missing value for argument: ", key)
      }
      value <- args[[i + 1L]]
      nm <- substring(key, 3L)
      out[[nm]] <- value
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }

  out
}

ensure_dir <- function(path) {
  dir.create(path, recursive = TRUE, showWarnings = FALSE)
  invisible(path)
}

message_block <- function(...) {
  cat("\n", paste0(..., collapse = ""), "\n", sep = "")
}
EOF

if [[ "$INIT_RENV" -eq 1 ]]; then
  RENVTEXT='
if (!requireNamespace("renv", quietly = TRUE)) {
  install.packages("renv")
}

if (!file.exists("renv.lock")) {
  renv::init(bare = TRUE)
} else {
  renv::activate()
}
'
else
  RENVTEXT=''
fi

cat > "$PROJECT_DIR/scripts/setup_env.R" <<EOF
# Run this to initialize the project environment.
# Add your project-specific package installs below.

${RENVTEXT}
required_pkgs <- c(
  "yaml"
)

missing_pkgs <- required_pkgs[!vapply(required_pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_pkgs) > 0) {
  install.packages(missing_pkgs)
}

# Add project-specific packages here, for example:
# install.packages(c("dplyr", "ggplot2", "data.table"))
# if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
# BiocManager::install(c("SingleCellExperiment"))

$( [[ "$INIT_RENV" -eq 1 ]] && cat <<'EOT'
renv::snapshot(prompt = FALSE)
EOT
)

message("Environment setup complete.")
EOF

cat > "$PROJECT_DIR/scripts/run_analysis.R" <<'EOF'
suppressPackageStartupMessages({
  if (file.exists("renv/activate.R")) source("renv/activate.R")
  source("R/utils.R")
})

args <- parse_args()
cfg  <- load_config(args$config)

ensure_dir("results")
ensure_dir("logs")

set.seed(cfg$seed %||% 123)

workers <- cfg$future_workers %||% 1

message_block("Starting analysis")
message("Working directory: ", getwd())
message("Project root: ", get_project_root())
message("Input: ", args$input %||% "<none>")
message("Output: ", args$output %||% "results/output.txt")

# ------------------------------------------------------------------
# TEMPLATE SECTION
# Replace this with your actual workflow.
# ------------------------------------------------------------------

output_path <- args$output %||% "results/output.txt"

lines <- c(
  paste("Timestamp:", Sys.time()),
  paste("Project:", cfg$project_name %||% "unknown"),
  paste("Working directory:", getwd()),
  paste("Input:", args$input %||% "<none>")
)

writeLines(lines, con = output_path)

message("Wrote output to: ", output_path)
message_block("Analysis complete")
EOF

cat > "$PROJECT_DIR/slurm/run_job.sh" <<EOF
#!/bin/bash
#SBATCH --job-name=${PROJECT_NAME}
#SBATCH --time=02:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=2
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

set -euo pipefail

module load R

PROJECT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
cd "\$PROJECT_DIR"

mkdir -p logs results

export OMP_NUM_THREADS="\${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="\${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="\${SLURM_CPUS_PER_TASK:-1}"

Rscript scripts/run_analysis.R
EOF

chmod +x "$PROJECT_DIR/slurm/run_job.sh"

if [[ "$INIT_RPROJ" -eq 1 ]]; then
  cat > "$PROJECT_DIR/${PROJECT_NAME}.Rproj" <<'EOF'
Version: 1.0

RestoreWorkspace: No
SaveWorkspace: No
AlwaysSaveHistory: Default

EnableCodeIndexing: Yes
UseSpacesForTab: Yes
NumSpacesForTab: 2
Encoding: UTF-8

RnwWeave: Sweave
LaTeX: pdfLaTeX
EOF
fi

python3 - <<PY
from pathlib import Path
p = Path("$PROJECT_DIR/config/analysis.yaml")
txt = p.read_text()
txt = txt.replace('project_name: "replace_me"', 'project_name: "$PROJECT_NAME"')
p.write_text(txt)
PY

if [[ "$INIT_GIT" -eq 1 ]]; then
  if command -v git >/dev/null 2>&1; then
    if [[ ! -d "$PROJECT_DIR/.git" ]]; then
      git -C "$PROJECT_DIR" init >/dev/null
    fi
  else
    echo "Warning: git not found; skipping git init." >&2
  fi
fi

echo "Initialized R project at: $PROJECT_DIR"

if [[ "$INIT_GIT" -eq 1 ]]; then
  echo "  - git: enabled"
fi
if [[ "$INIT_RENV" -eq 1 ]]; then
  echo "  - renv bootstrap: enabled"
fi
if [[ "$INIT_RPROJ" -eq 1 ]]; then
  echo "  - RStudio project file: created"
fi

cat <<EOF

Next steps:
  cd $PROJECT_DIR
  R
  source("scripts/setup_env.R")

Or from the shell:
  cd $PROJECT_DIR
  Rscript scripts/run_analysis.R
EOF