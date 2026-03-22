#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/templates"

usage() {
  cat <<'EOF'
Usage:
  r-init <project_name> [options]

Options:
  --no-git      Skip git initialization (default: git enabled)
  --no-renv     Skip renv bootstrap (default: renv enabled)
  --rproj       Create an RStudio .Rproj file
  --slurm       Include SLURM job template
  --force       Allow creation in a non-empty directory
  -h, --help    Show this help message

Examples:
  r-init my_analysis
  r-init my_analysis --rproj --slurm
  r-init my_analysis --no-renv
EOF
}

# --- Helpers ----------------------------------------------------------------

copy_template() {
  cp "$TEMPLATE_DIR/$1" "$PROJECT_DIR/$2"
}

render_template() {
  sed -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
    "$TEMPLATE_DIR/$1" > "$PROJECT_DIR/$2"
}

log_item() {
  printf "  %s %s\n" "$1" "$2"
}

# --- Parse arguments --------------------------------------------------------

PROJECT_NAME=""
INIT_GIT=1
INIT_RENV=1
INIT_RPROJ=0
INIT_SLURM=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-git)   INIT_GIT=0;  shift ;;
    --no-renv)  INIT_RENV=0; shift ;;
    --rproj)    INIT_RPROJ=1; shift ;;
    --slurm)    INIT_SLURM=1; shift ;;
    --force)    FORCE=1;     shift ;;
    -h|--help)  usage; exit 0 ;;
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

# --- Validate target directory ----------------------------------------------

if [[ -e "$PROJECT_DIR" ]]; then
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "Error: $PROJECT_DIR exists and is not a directory." >&2
    exit 1
  fi
  if [[ "$FORCE" -ne 1 ]] && [[ -n "$(ls -A "$PROJECT_DIR" 2>/dev/null)" ]]; then
    echo "Error: $PROJECT_DIR already exists and is not empty. Use --force to continue." >&2
    exit 1
  fi
fi

# --- Create directory structure ---------------------------------------------

dirs=(R scripts config data results logs docs tests)
if [[ "$INIT_SLURM" -eq 1 ]]; then
  dirs+=(slurm)
fi

for d in "${dirs[@]}"; do
  mkdir -p "$PROJECT_DIR/$d"
done

touch "$PROJECT_DIR/tests/.gitkeep"

# --- Copy templates ---------------------------------------------------------

copy_template   "gitignore"              ".gitignore"
copy_template   "Rprofile"               ".Rprofile"
copy_template   "R/utils.R"              "R/utils.R"
copy_template   "scripts/run_analysis.R" "scripts/run_analysis.R"

render_template "README.md.tmpl"              "README.md"
render_template "config/analysis.yaml.tmpl"   "config/analysis.yaml"

# setup_env.R — conditionally inject renv blocks
if [[ "$INIT_RENV" -eq 1 ]]; then
  {
    cat "$TEMPLATE_DIR/scripts/setup_env_renv.snippet"
    sed -e '/{{RENV_BLOCK}}/d' \
        -e 's|{{RENV_SNAPSHOT}}|renv::snapshot(prompt = FALSE)|g' \
        "$TEMPLATE_DIR/scripts/setup_env.R"
  } > "$PROJECT_DIR/scripts/setup_env.R"
else
  sed -e '/{{RENV_BLOCK}}/d' \
      -e '/{{RENV_SNAPSHOT}}/d' \
      "$TEMPLATE_DIR/scripts/setup_env.R" > "$PROJECT_DIR/scripts/setup_env.R"
fi

# slurm (opt-in)
if [[ "$INIT_SLURM" -eq 1 ]]; then
  render_template "slurm/run_job.sh.tmpl" "slurm/run_job.sh"
  chmod +x "$PROJECT_DIR/slurm/run_job.sh"
fi

# .Rproj (opt-in)
if [[ "$INIT_RPROJ" -eq 1 ]]; then
  copy_template "Rproj.tmpl" "${PROJECT_NAME}.Rproj"
fi

# --- Git init ---------------------------------------------------------------

if [[ "$INIT_GIT" -eq 1 ]]; then
  if command -v git >/dev/null 2>&1; then
    if [[ ! -d "$PROJECT_DIR/.git" ]]; then
      git -C "$PROJECT_DIR" init -q
    fi
  else
    echo "Warning: git not found; skipping git init." >&2
  fi
fi

# --- Summary ----------------------------------------------------------------

echo "Initialized R project: $PROJECT_DIR"

[[ "$INIT_GIT"   -eq 1 ]] && log_item "+" "git"
[[ "$INIT_RENV"  -eq 1 ]] && log_item "+" "renv"
[[ "$INIT_RPROJ" -eq 1 ]] && log_item "+" "RStudio .Rproj"
[[ "$INIT_SLURM" -eq 1 ]] && log_item "+" "SLURM template"

cat <<EOF

Next steps:
  cd $PROJECT_DIR
  Rscript scripts/setup_env.R
EOF
