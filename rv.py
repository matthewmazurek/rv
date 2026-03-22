#!/usr/bin/env python3
"""rv — lightweight R project manager."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RV_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = RV_DIR / "templates"
SETUP_ENV = Path("scripts/setup_env.R")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PKGS_PATTERN = re.compile(
    r"(required_pkgs\s*<-\s*c\()([^)]*?)(\))", re.DOTALL
)

Pkg = tuple[str, str | None]  # (name, version_or_None)


def parse_pkg_spec(spec: str) -> Pkg:
    """Parse a CLI spec like 'Seurat==4.4.0' into (name, version)."""
    if "==" in spec:
        name, version = spec.split("==", 1)
        return name, version
    return spec, None


def parse_pkg_list(text: str) -> list[Pkg]:
    """Extract (name, version) tuples from the required_pkgs <- c(...) block."""
    m = PKGS_PATTERN.search(text)
    if not m:
        return []
    entries = re.findall(r'"([^"]+)"', m.group(2))
    result: list[Pkg] = []
    for e in entries:
        if "@" in e:
            name, ver = e.split("@", 1)
            result.append((name, ver))
        else:
            result.append((e, None))
    return result


def pkg_names(pkgs: list[Pkg]) -> list[str]:
    """Return just the names from a package list."""
    return [name for name, _ in pkgs]


def format_pkg_entry(name: str, version: str | None) -> str:
    return f'  "{name}@{version}"' if version else f'  "{name}"'


def format_pkg_list(pkgs: list[Pkg]) -> str:
    """Format a package list as R c() body."""
    if not pkgs:
        return "required_pkgs <- c()"
    entries = ",\n".join(format_pkg_entry(n, v) for n, v in pkgs)
    return f"required_pkgs <- c(\n{entries}\n)"


def replace_pkg_list(text: str, pkgs: list[Pkg]) -> str:
    """Replace the required_pkgs <- c(...) block in-place."""
    return PKGS_PATTERN.sub(format_pkg_list(pkgs), text)


def pak_spec(name: str, version: str | None) -> str:
    """Build a pak-compatible install spec."""
    return f"{name}@{version}" if version else name


def require_project():
    """Exit if not inside an rv project."""
    if not SETUP_ENV.exists():
        sys.exit(f"Error: {SETUP_ENV} not found. Are you in an rv project?")


def rscript(*args: str) -> subprocess.CompletedProcess:
    """Run Rscript with the given arguments."""
    return subprocess.run(["Rscript", *args])


def renv_snapshot():
    """Snapshot renv if a lockfile exists."""
    if Path("renv.lock").exists():
        print("Updating renv.lock...")
        rscript("-e", "renv::snapshot(prompt = FALSE)")


# ---------------------------------------------------------------------------
# rv init
# ---------------------------------------------------------------------------

def copy_template(src: str, dest: Path):
    shutil.copy2(TEMPLATE_DIR / src, dest)


def render_template(src: str, dest: Path, variables: dict[str, str]):
    text = (TEMPLATE_DIR / src).read_text()
    for key, val in variables.items():
        text = text.replace(f"{{{{{key}}}}}", val)
    dest.write_text(text)


def cmd_init(args):
    project = Path(args.name)

    if project.exists():
        if not project.is_dir():
            sys.exit(f"Error: {project} exists and is not a directory.")
        if not args.force and any(project.iterdir()):
            sys.exit(
                f"Error: {project} already exists and is not empty. "
                "Use --force to continue."
            )

    dirs = ["R", "scripts", "config", "data", "results", "logs", "docs", "tests"]
    if args.slurm:
        dirs.append("slurm")
    for d in dirs:
        (project / d).mkdir(parents=True, exist_ok=True)
    (project / "tests" / ".gitkeep").touch()

    variables = {"PROJECT_NAME": args.name}

    # Verbatim copies
    copy_template("gitignore", project / ".gitignore")
    copy_template("Rprofile", project / ".Rprofile")
    copy_template("R/utils.R", project / "R" / "utils.R")
    copy_template("scripts/run_analysis.R", project / "scripts" / "run_analysis.R")

    # Rendered templates
    render_template("README.md.tmpl", project / "README.md", variables)
    render_template("config/analysis.yaml.tmpl", project / "config" / "analysis.yaml", variables)

    # setup_env.R with conditional renv injection
    setup_text = (TEMPLATE_DIR / "scripts" / "setup_env.R").read_text()
    if args.renv:
        renv_block = (TEMPLATE_DIR / "scripts" / "setup_env_renv.snippet").read_text()
        setup_text = setup_text.replace("{{RENV_BLOCK}}\n", renv_block)
        setup_text = setup_text.replace("{{RENV_SNAPSHOT}}", "renv::snapshot(prompt = FALSE)")
    else:
        setup_text = setup_text.replace("{{RENV_BLOCK}}\n", "")
        setup_text = setup_text.replace("{{RENV_SNAPSHOT}}\n", "")
    (project / "scripts" / "setup_env.R").write_text(setup_text)

    # Optional: slurm
    if args.slurm:
        render_template("slurm/run_job.sh.tmpl", project / "slurm" / "run_job.sh", variables)
        (project / "slurm" / "run_job.sh").chmod(0o755)

    # Optional: Rproj
    if args.rproj:
        copy_template("Rproj.tmpl", project / f"{args.name}.Rproj")

    # Git init
    if args.git:
        if shutil.which("git"):
            if not (project / ".git").exists():
                subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        else:
            print("Warning: git not found; skipping git init.", file=sys.stderr)

    # Sync (install packages + bootstrap renv)
    if args.sync:
        print(f"Setting up environment...")
        result = subprocess.run(
            ["Rscript", "scripts/setup_env.R"],
            cwd=str(project),
        )
        if result.returncode != 0:
            print("Warning: setup_env.R failed. Run 'rv sync' to retry.", file=sys.stderr)

    # Summary
    print(f"\nInitialized R project: {project}")
    if args.git:
        print("  + git")
    if args.renv:
        print("  + renv")
    if args.rproj:
        print("  + RStudio .Rproj")
    if args.slurm:
        print("  + SLURM template")
    print(f"\n  cd {project}")


# ---------------------------------------------------------------------------
# rv add
# ---------------------------------------------------------------------------

def cmd_add(args):
    require_project()
    text = SETUP_ENV.read_text()
    pkgs = parse_pkg_list(text)
    names = pkg_names(pkgs)

    added: list[Pkg] = []
    skipped: list[str] = []

    for raw in args.packages:
        name, version = parse_pkg_spec(raw)
        if args.bioc and version:
            print(
                f"Warning: --bioc ignores version pin for {name}; "
                "Bioconductor versions are tied to Bioc releases.",
                file=sys.stderr,
            )
            version = None
        if name in names:
            skipped.append(name)
        else:
            pkgs.append((name, version))
            names.append(name)
            added.append((name, version))

    if not added:
        print("Nothing to add — all packages already listed.")
        return

    SETUP_ENV.write_text(replace_pkg_list(text, pkgs))

    print(f"Installing {len(added)} package(s)...")
    if args.bioc:
        bioc_pkgs = ", ".join(f'"{n}"' for n, _ in added)
        expr = (
            'if (!requireNamespace("BiocManager", quietly = TRUE)) '
            'install.packages("BiocManager"); '
            f'BiocManager::install(c({bioc_pkgs}))'
        )
        rscript("-e", expr)
    else:
        specs = ", ".join(f'"{pak_spec(n, v)}"' for n, v in added)
        expr = (
            'if (!requireNamespace("pak", quietly = TRUE)) '
            'install.packages("pak"); '
            f'pak::pkg_install(c({specs}))'
        )
        rscript("-e", expr)

    renv_snapshot()

    for name, ver in added:
        label = f"{name}=={ver}" if ver else name
        print(f"  + {label}")
    for name in skipped:
        print(f"  ~ {name} (already listed)")


# ---------------------------------------------------------------------------
# rv rm
# ---------------------------------------------------------------------------

def cmd_rm(args):
    require_project()
    text = SETUP_ENV.read_text()
    pkgs = parse_pkg_list(text)

    removed: list[str] = []
    not_found: list[str] = []
    for name in args.packages:
        matched = [(n, v) for n, v in pkgs if n == name]
        if matched:
            for entry in matched:
                pkgs.remove(entry)
            removed.append(name)
        else:
            not_found.append(name)

    if not removed:
        print("Nothing to remove — none of the packages are listed.")
        return

    SETUP_ENV.write_text(replace_pkg_list(text, pkgs))
    renv_snapshot()

    for p in removed:
        print(f"  - {p}")
    for p in not_found:
        print(f"  ~ {p} (not found)")


# ---------------------------------------------------------------------------
# rv sync
# ---------------------------------------------------------------------------

def cmd_sync(args):
    require_project()
    print("Running scripts/setup_env.R...")
    result = rscript(str(SETUP_ENV))
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# rv run
# ---------------------------------------------------------------------------

def cmd_run(args):
    script = args.script or "scripts/run_analysis.R"
    if not Path(script).exists():
        sys.exit(f"Error: {script} not found.")
    result = rscript(script, *args.extra)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="rv", description="Lightweight R project manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # rv init
    p_init = sub.add_parser("init", help="Create a new R project")
    p_init.add_argument("name", help="Project name (becomes directory name)")
    p_init.add_argument("--no-git", dest="git", action="store_false", default=True)
    p_init.add_argument("--no-renv", dest="renv", action="store_false", default=True)
    p_init.add_argument("--rproj", action="store_true", help="Create .Rproj file")
    p_init.add_argument("--slurm", action="store_true", help="Include SLURM template")
    p_init.add_argument("--force", action="store_true", help="Allow non-empty directory")
    p_init.add_argument("--no-sync", dest="sync", action="store_false", default=True,
                        help="Skip running setup_env.R after init")
    p_init.set_defaults(func=cmd_init)

    # rv add
    p_add = sub.add_parser("add", help="Add packages to the project")
    p_add.add_argument("packages", nargs="+", help="Package name(s)")
    p_add.add_argument("--bioc", action="store_true", help="Install from Bioconductor")
    p_add.set_defaults(func=cmd_add)

    # rv rm
    p_rm = sub.add_parser("rm", help="Remove packages from the project")
    p_rm.add_argument("packages", nargs="+", help="Package name(s)")
    p_rm.set_defaults(func=cmd_rm)

    # rv sync
    p_sync = sub.add_parser("sync", help="Install all listed packages")
    p_sync.set_defaults(func=cmd_sync)

    # rv run
    p_run = sub.add_parser("run", help="Run an R script")
    p_run.add_argument("script", nargs="?", help="Script path (default: scripts/run_analysis.R)")
    p_run.add_argument("extra", nargs="*", help="Extra arguments passed to Rscript")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
