#!/usr/bin/env python3
"""rv — lightweight R project manager."""

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

RV_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = RV_DIR / "templates"
RV_CONFIG = Path("rproject.toml")

__version__: str | None = None


def get_version() -> str:
    global __version__
    if __version__ is None:
        try:
            result = subprocess.run(
                ["git", "-C", str(RV_DIR), "describe", "--tags", "--always"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            __version__ = (
                result.stdout.strip()
                if result.returncode == 0 and result.stdout.strip()
                else "dev"
            )
        except Exception:
            __version__ = "dev"
    return __version__


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

Pkg = tuple[str, str | None]  # (name, version_or_None)


def parse_pkg_spec(spec: str) -> Pkg:
    """Parse a CLI spec like 'Seurat==4.4.0' into (name, version)."""
    if "==" in spec:
        name, version = spec.split("==", 1)
        return name, version
    return spec, None


def pkg_names(pkgs: list[Pkg]) -> list[str]:
    """Return just the names from a package list."""
    return [name for name, _ in pkgs]


def pak_spec(name: str, version: str | None) -> str:
    """Build a pak-compatible install spec."""
    return f"{name}@{version}" if version else name


def require_project():
    """Exit if not inside an rv project."""
    if not RV_CONFIG.exists():
        sys.exit(f"Error: {RV_CONFIG} not found. Are you in an rv project?")


# ---------------------------------------------------------------------------
# rproject.toml config
# ---------------------------------------------------------------------------


def read_rv_config(path: Path | None = None) -> dict:
    """Read rproject.toml."""
    path = path or RV_CONFIG
    if not path.exists():
        return {"renv": True, "packages": []}
    with open(path, "rb") as f:
        return tomllib.load(f)


def write_rv_config(config: dict, path: Path | None = None):
    """Write rproject.toml."""
    path = path or RV_CONFIG
    lines: list[str] = []
    tables: list[tuple[str, dict]] = []

    for key, value in config.items():
        if isinstance(value, dict):
            tables.append((key, value))
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key} = []")
            elif len(value) == 1:
                lines.append(f'{key} = ["{value[0]}"]')
            else:
                items = ",\n".join(f'    "{item}"' for item in value)
                lines.append(f"{key} = [\n{items},\n]")
        else:
            lines.append(f'{key} = "{value}"')

    for table_name, table_dict in tables:
        lines.append("")
        lines.append(f"[{table_name}]")
        for k, v in table_dict.items():
            lines.append(f'{k} = "{v}"')

    path.write_text("\n".join(lines) + "\n")


def config_to_pkgs(config: dict) -> list[Pkg]:
    """Extract (name, version) tuples from config packages list."""
    result: list[Pkg] = []
    for entry in config.get("packages", []):
        if "@" in entry:
            name, ver = entry.split("@", 1)
            result.append((name, ver))
        else:
            result.append((entry, None))
    return result


def pkgs_to_entries(pkgs: list[Pkg]) -> list[str]:
    """Convert (name, version) tuples to pak-style strings."""
    return [pak_spec(name, ver) for name, ver in pkgs]


# ---------------------------------------------------------------------------
# R code generation
# ---------------------------------------------------------------------------


def build_sync_script(config: dict) -> str:
    """Generate R code to install all packages from rproject.toml."""
    lines: list[str] = []

    if config.get("renv", False):
        lines.extend(
            [
                'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv")',
                "",
                'if (!file.exists("renv.lock")) {',
                "  renv::init(bare = TRUE)",
                "} else {",
                "  renv::activate()",
                "}",
                "",
            ]
        )

    lines.append(
        'if (!requireNamespace("pak", quietly = TRUE)) install.packages("pak")'
    )

    pkgs = config.get("packages", [])
    if pkgs:
        specs = ", ".join(f'"{p}"' for p in pkgs)
        lines.append(f"pak::pkg_install(c({specs}))")

    if config.get("renv", False):
        lines.append("")
        lines.append("renv::snapshot(prompt = FALSE)")

    lines.append("")
    lines.append('message("Environment setup complete.")')
    return "\n".join(lines)


def run_r_code(code: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run R code via Rscript stdin."""
    return subprocess.run(["Rscript", "-"], input=code, text=True, cwd=cwd)


# ---------------------------------------------------------------------------
# Script aliases
# ---------------------------------------------------------------------------


def load_script_aliases() -> dict[str, str]:
    """Load script aliases from rproject.toml."""
    if not RV_CONFIG.exists():
        return {}
    config = read_rv_config()
    scripts = config.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def rscript(*args: str) -> subprocess.CompletedProcess:
    """Run Rscript with the given arguments."""
    return subprocess.run(["Rscript", *args])


def renv_snapshot() -> bool:
    """Snapshot renv if enabled and lockfile exists.

    Returns True if snapshot succeeded or was skipped, False on failure.
    On failure, attempts to restore missing dependencies and retry once.
    """
    if RV_CONFIG.exists():
        config = read_rv_config()
        if not config.get("renv", False):
            return True
    if not Path("renv.lock").exists():
        return True

    print("Updating renv.lock...")
    result = rscript("-e", "renv::snapshot(prompt = FALSE)")
    if result.returncode == 0:
        return True

    print(
        "Snapshot failed — attempting to restore missing dependencies...",
        file=sys.stderr,
    )
    repair = rscript("-e", "renv::install()")
    if repair.returncode == 0:
        result = rscript("-e", "renv::snapshot(prompt = FALSE)")
        if result.returncode == 0:
            return True

    print(
        "Warning: renv.lock was NOT updated. Run `renv::status()` in R for details.",
        file=sys.stderr,
    )
    return False


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
    if args.name == ".":
        project = Path.cwd()
        project_name = project.name
    else:
        project = Path(args.name)
        project_name = project.name

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

    variables = {"PROJECT_NAME": project_name}

    # Verbatim copies
    copy_template("gitignore", project / ".gitignore")
    copy_template("Rprofile", project / ".Rprofile")
    copy_template("R/utils.R", project / "R" / "utils.R")
    copy_template("R/init.R", project / "R" / "init.R")
    copy_template("scripts/run_analysis.R", project / "scripts" / "run_analysis.R")

    # Rendered templates
    render_template("README.md.tmpl", project / "README.md", variables)
    config_tmpl = (
        "config/analysis.yaml.slurm.tmpl" if args.slurm else "config/analysis.yaml.tmpl"
    )
    render_template(config_tmpl, project / "config" / "analysis.yaml", variables)

    # Optional: slurm
    default_script = "scripts/run_analysis.R"
    if args.slurm:
        copy_template(
            "scripts/slurm_analysis.R", project / "scripts" / "slurm_analysis.R"
        )
        render_template(
            "slurm/run_job.sh.tmpl", project / "slurm" / "run_job.sh", variables
        )
        (project / "slurm" / "run_job.sh").chmod(0o755)
        default_script = "scripts/slurm_analysis.R"

    # rproject.toml
    config = {
        "renv": args.renv,
        "packages": ["yaml"],
        "scripts": {"default": default_script},
    }
    write_rv_config(config, project / "rproject.toml")

    # Optional: Rproj
    if args.rproj:
        copy_template("Rproj.tmpl", project / f"{project_name}.Rproj")

    # Optional: Docker
    if args.docker:
        render_template("docker/Dockerfile.tmpl", project / "Dockerfile", variables)

    # Optional: Apptainer
    if args.apptainer:
        render_template(
            "docker/Apptainer.def.tmpl", project / f"{project_name}.def", variables
        )

    # Optional: CI
    if args.ci:
        (project / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        render_template(
            "ci/r-check.yml.tmpl",
            project / ".github" / "workflows" / "r-check.yml",
            variables,
        )

    # Git init
    if args.git:
        if shutil.which("git"):
            if not (project / ".git").exists():
                subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        else:
            print("Warning: git not found; skipping git init.", file=sys.stderr)

    # Sync (install packages + bootstrap renv)
    if args.sync:
        print("Setting up environment...")
        script = build_sync_script(config)
        result = run_r_code(script, cwd=str(project))
        if result.returncode != 0:
            print(
                "Warning: environment setup failed. Run 'rv sync' to retry.",
                file=sys.stderr,
            )

    # Summary
    print(f"\nInitialized R project: {project_name}")
    if args.git:
        print("  + git")
    if args.renv:
        print("  + renv")
    if args.rproj:
        print("  + RStudio .Rproj")
    if args.slurm:
        print("  + SLURM template")
    if args.docker:
        print("  + Dockerfile")
    if args.apptainer:
        print("  + Apptainer definition")
    if args.ci:
        print("  + GitHub Actions CI")
    if args.name != ".":
        print(f"\n  cd {project}")


# ---------------------------------------------------------------------------
# rv add
# ---------------------------------------------------------------------------


def cmd_add(args):
    require_project()
    config = read_rv_config()
    pkgs = config_to_pkgs(config)
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

    config["packages"] = pkgs_to_entries(pkgs)
    write_rv_config(config)

    print(f"Installing {len(added)} package(s)...")
    if args.bioc:
        bioc_pkgs = ", ".join(f'"{n}"' for n, _ in added)
        expr = (
            'if (!requireNamespace("BiocManager", quietly = TRUE)) '
            'install.packages("BiocManager"); '
            f"BiocManager::install(c({bioc_pkgs}))"
        )
        result = rscript("-e", expr)
    else:
        specs = ", ".join(f'"{pak_spec(n, v)}"' for n, v in added)
        expr = (
            'if (!requireNamespace("pak", quietly = TRUE)) '
            'install.packages("pak"); '
            f"pak::pkg_install(c({specs}))"
        )
        result = rscript("-e", expr)

    if result.returncode != 0:
        print("Error: package installation failed.", file=sys.stderr)
        sys.exit(result.returncode)

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
    config = read_rv_config()
    pkgs = config_to_pkgs(config)

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

    config["packages"] = pkgs_to_entries(pkgs)
    write_rv_config(config)
    renv_snapshot()

    for p in removed:
        print(f"  - {p}")
    for p in not_found:
        print(f"  ~ {p} (not found)")


# ---------------------------------------------------------------------------
# rv list
# ---------------------------------------------------------------------------


def cmd_list(args):
    require_project()
    pkgs = config_to_pkgs(read_rv_config())
    if not pkgs:
        print("No packages listed.")
        return
    for name, ver in pkgs:
        print(f"{name}=={ver}" if ver else name)


# ---------------------------------------------------------------------------
# rv update
# ---------------------------------------------------------------------------


def cmd_update(args):
    require_project()
    config = read_rv_config()
    pkgs = config_to_pkgs(config)

    if not pkgs:
        print("No packages listed.")
        return

    if args.packages:
        names_to_update = set(args.packages)
        not_found = names_to_update - {n for n, _ in pkgs}
        for name in not_found:
            print(f"  ~ {name} (not found)")
        targets = [(n, v) for n, v in pkgs if n in names_to_update]
        pkgs = [(n, None if n in names_to_update else v) for n, v in pkgs]
    else:
        targets = pkgs
        pkgs = [(n, None) for n, _ in pkgs]

    if not targets:
        print("Nothing to update.")
        return

    config["packages"] = pkgs_to_entries(pkgs)
    write_rv_config(config)

    specs = ", ".join(f'"{n}"' for n, _ in targets)
    expr = (
        'if (!requireNamespace("pak", quietly = TRUE)) '
        'install.packages("pak"); '
        f"pak::pkg_install(c({specs}))"
    )
    print(f"Updating {len(targets)} package(s)...")
    result = rscript("-e", expr)

    if result.returncode != 0:
        print("Error: package update failed.", file=sys.stderr)
        sys.exit(result.returncode)

    renv_snapshot()

    for name, _ in targets:
        print(f"  ^ {name}")


# ---------------------------------------------------------------------------
# rv sync
# ---------------------------------------------------------------------------


def sync_packages() -> int:
    """Sync packages from rproject.toml. Returns the process exit code."""
    config = read_rv_config()
    print("Syncing packages...")
    script = build_sync_script(config)
    return run_r_code(script).returncode


def cmd_sync(args):
    require_project()
    sys.exit(sync_packages())


# ---------------------------------------------------------------------------
# rv run
# ---------------------------------------------------------------------------


def cmd_run(args):
    if args.sync and RV_CONFIG.exists():
        rc = sync_packages()
        if rc != 0:
            sys.exit(rc)

    aliases = load_script_aliases()
    name = args.script

    if name is None:
        script = aliases.get("default", "scripts/run_analysis.R")
    elif name in aliases:
        script = aliases[name]
    else:
        script = name

    if not Path(script).exists():
        if name and name in aliases:
            sys.exit(
                f"Error: script alias '{name}' points to {script}, which was not found."
            )
        sys.exit(f"Error: {script} not found.")

    extra = args.extra
    if extra and extra[0] == "--":
        extra = extra[1:]
    result = rscript(script, *extra)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# rv clean
# ---------------------------------------------------------------------------


def _clear_dir(path: Path) -> int:
    """Remove all contents of a directory, return count of items removed."""
    count = 0
    for child in path.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        count += 1
    return count


def cmd_clean(args):
    require_project()
    cleaned: list[str] = []

    for dirname in ("results", "logs"):
        d = Path(dirname)
        if d.is_dir():
            n = _clear_dir(d)
            if n:
                cleaned.append(f"  - {dirname}/ ({n} item(s))")

    if args.renv:
        for renv_sub in ("renv/library", "renv/staging"):
            p = Path(renv_sub)
            if p.is_dir():
                shutil.rmtree(p)
                cleaned.append(f"  - {renv_sub}/")

    if cleaned:
        print("Cleaned:")
        for line in cleaned:
            print(line)
    else:
        print("Nothing to clean.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="rv", description="Lightweight R project manager"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # rv init
    p_init = sub.add_parser("init", help="Create a new R project")
    p_init.add_argument(
        "name", help="Project name (becomes directory name, or '.' for current dir)"
    )
    p_init.add_argument("--no-git", dest="git", action="store_false", default=True)
    p_init.add_argument("--no-renv", dest="renv", action="store_false", default=True)
    p_init.add_argument("--rproj", action="store_true", help="Create .Rproj file")
    p_init.add_argument("--slurm", action="store_true", help="Include SLURM template")
    p_init.add_argument("--docker", action="store_true", help="Include Dockerfile")
    p_init.add_argument(
        "--apptainer", action="store_true", help="Include Apptainer definition"
    )
    p_init.add_argument(
        "--ci", action="store_true", help="Include GitHub Actions CI workflow"
    )
    p_init.add_argument(
        "--force", action="store_true", help="Allow non-empty directory"
    )
    p_init.add_argument(
        "--no-sync",
        dest="sync",
        action="store_false",
        default=True,
        help="Skip initial package sync",
    )
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

    # rv list
    p_list = sub.add_parser("list", help="List declared packages")
    p_list.set_defaults(func=cmd_list)

    # rv update
    p_update = sub.add_parser("update", help="Update packages to latest versions")
    p_update.add_argument(
        "packages", nargs="*", help="Package(s) to update (default: all)"
    )
    p_update.set_defaults(func=cmd_update)

    # rv sync
    p_sync = sub.add_parser("sync", help="Install all listed packages")
    p_sync.set_defaults(func=cmd_sync)

    # rv run
    p_run = sub.add_parser("run", help="Run an R script")
    p_run.add_argument(
        "script", nargs="?", help="Script path (default: scripts/run_analysis.R)"
    )
    p_run.add_argument(
        "extra", nargs=argparse.REMAINDER, help="Extra arguments passed to Rscript"
    )
    p_run.add_argument(
        "--no-sync",
        dest="sync",
        action="store_false",
        default=True,
        help="Skip automatic package sync before running",
    )
    p_run.set_defaults(func=cmd_run)

    # rv clean
    p_clean = sub.add_parser("clean", help="Remove generated outputs")
    p_clean.add_argument(
        "--renv", action="store_true", help="Also clean renv library cache"
    )
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
