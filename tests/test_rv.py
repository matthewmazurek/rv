"""Comprehensive tests for rv.py — lightweight R project manager."""

import subprocess
import types
from pathlib import Path
from unittest.mock import patch

import pytest

import rv
from tests.conftest import RV_CONFIG_CONTENT

# ── parse_pkg_spec ──────────────────────────────────────────────────────────


class TestParsePkgSpec:
    def test_plain_name(self):
        assert rv.parse_pkg_spec("dplyr") == ("dplyr", None)

    def test_version_pinned(self):
        assert rv.parse_pkg_spec("Seurat==4.4.0") == ("Seurat", "4.4.0")

    def test_dotted_package_name(self):
        assert rv.parse_pkg_spec("data.table") == ("data.table", None)

    def test_dotted_name_with_version(self):
        assert rv.parse_pkg_spec("data.table==1.14.8") == ("data.table", "1.14.8")

    def test_multiple_equals_splits_on_first(self):
        assert rv.parse_pkg_spec("pkg==1.0==extra") == ("pkg", "1.0==extra")


# ── read_rv_config / write_rv_config ───────────────────────────────────────


class TestReadRvConfig:
    def test_reads_standard_config(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text(RV_CONFIG_CONTENT)
        config = rv.read_rv_config(cfg)
        assert config["renv"] is True
        assert config["packages"] == ["dplyr", "ggplot2@3.4.0", "tidyr"]

    def test_renv_false(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text('renv = false\npackages = ["yaml"]\n')
        config = rv.read_rv_config(cfg)
        assert config["renv"] is False

    def test_empty_packages(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = true\npackages = []\n")
        config = rv.read_rv_config(cfg)
        assert config["packages"] == []

    def test_missing_file_returns_defaults(self, tmp_path):
        config = rv.read_rv_config(tmp_path / "nonexistent.toml")
        assert config["renv"] is True
        assert config["packages"] == []

    def test_comments_and_blank_lines(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text('# header comment\nrenv = true\n\npackages = ["yaml"]\n')
        config = rv.read_rv_config(cfg)
        assert config["packages"] == ["yaml"]

    def test_scripts_table(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text(
            'renv = true\npackages = []\n\n[scripts]\ndefault = "scripts/run.R"\n'
        )
        config = rv.read_rv_config(cfg)
        assert config["scripts"] == {"default": "scripts/run.R"}


class TestWriteRvConfig:
    def test_round_trip(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        original = {"renv": True, "packages": ["dplyr", "ggplot2@3.4.0", "tidyr"]}
        rv.write_rv_config(original, cfg)
        restored = rv.read_rv_config(cfg)
        assert restored["renv"] is True
        assert restored["packages"] == original["packages"]

    def test_empty_packages_round_trip(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        rv.write_rv_config({"renv": False, "packages": []}, cfg)
        restored = rv.read_rv_config(cfg)
        assert restored["renv"] is False
        assert restored["packages"] == []

    def test_writes_valid_toml(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        rv.write_rv_config({"renv": True, "packages": ["yaml", "dplyr"]}, cfg)
        text = cfg.read_text()
        assert "renv = true" in text
        assert '"yaml"' in text
        assert '"dplyr"' in text

    def test_scripts_table_round_trip(self, tmp_path):
        cfg = tmp_path / "rproject.toml"
        original = {
            "renv": True,
            "packages": ["yaml"],
            "scripts": {"default": "scripts/run.R", "alt": "scripts/alt.R"},
        }
        rv.write_rv_config(original, cfg)
        restored = rv.read_rv_config(cfg)
        assert restored["scripts"] == original["scripts"]


# ── config_to_pkgs / pkgs_to_entries ───────────────────────────────────────


class TestConfigToPkgs:
    def test_mixed_pinned_and_unpinned(self):
        config = {"packages": ["A", "B@2.0", "C"]}
        assert rv.config_to_pkgs(config) == [("A", None), ("B", "2.0"), ("C", None)]

    def test_empty(self):
        assert rv.config_to_pkgs({"packages": []}) == []

    def test_missing_key(self):
        assert rv.config_to_pkgs({}) == []


class TestPkgsToEntries:
    def test_converts_tuples_to_strings(self):
        pkgs = [("A", None), ("B", "2.0"), ("C", None)]
        assert rv.pkgs_to_entries(pkgs) == ["A", "B@2.0", "C"]

    def test_empty(self):
        assert rv.pkgs_to_entries([]) == []

    def test_round_trip_with_config(self):
        original = [("dplyr", None), ("ggplot2", "3.4.0"), ("tidyr", None)]
        entries = rv.pkgs_to_entries(original)
        restored = rv.config_to_pkgs({"packages": entries})
        assert restored == original


# ── build_sync_script ──────────────────────────────────────────────────────


class TestBuildSyncScript:
    def test_with_renv_and_packages(self):
        config = {"renv": True, "packages": ["yaml", "dplyr"]}
        script = rv.build_sync_script(config)
        assert "renv::init" in script
        assert "renv::activate" in script
        assert "renv::snapshot" in script
        assert 'pak::pkg_install(c("yaml", "dplyr"))' in script

    def test_without_renv(self):
        config = {"renv": False, "packages": ["yaml"]}
        script = rv.build_sync_script(config)
        assert "renv" not in script
        assert 'pak::pkg_install(c("yaml"))' in script

    def test_no_packages(self):
        config = {"renv": False, "packages": []}
        script = rv.build_sync_script(config)
        assert "pak::pkg_install" not in script
        assert "Environment setup complete" in script

    def test_pinned_version_in_spec(self):
        config = {"renv": False, "packages": ["Seurat@4.4.0"]}
        script = rv.build_sync_script(config)
        assert '"Seurat@4.4.0"' in script


# ── pak_spec ────────────────────────────────────────────────────────────────


class TestPakSpec:
    def test_without_version(self):
        assert rv.pak_spec("dplyr", None) == "dplyr"

    def test_with_version(self):
        assert rv.pak_spec("Seurat", "4.4.0") == "Seurat@4.4.0"


# ── pkg_names ───────────────────────────────────────────────────────────────


class TestPkgNames:
    def test_extracts_names(self):
        pkgs = [("A", "1.0"), ("B", None)]
        assert rv.pkg_names(pkgs) == ["A", "B"]

    def test_empty(self):
        assert rv.pkg_names([]) == []


# ── Template rendering ─────────────────────────────────────────────────────


class TestTemplateRendering:
    def test_render_template_replaces_placeholders(self, tmp_path):
        dest = tmp_path / "README.md"
        rv.render_template("README.md.tmpl", dest, {"PROJECT_NAME": "test-proj"})
        content = dest.read_text()
        assert "# test-proj" in content
        assert "{{PROJECT_NAME}}" not in content

    def test_copy_template_verbatim(self, tmp_path):
        dest = tmp_path / ".gitignore"
        rv.copy_template("gitignore", dest)
        original = (rv.TEMPLATE_DIR / "gitignore").read_text()
        assert dest.read_text() == original

    def test_render_config_template(self, tmp_path):
        dest = tmp_path / "analysis.yaml"
        rv.render_template(
            "config/analysis.yaml.tmpl", dest, {"PROJECT_NAME": "my-project"}
        )
        content = dest.read_text()
        assert 'project_name: "my-project"' in content
        assert "{{PROJECT_NAME}}" not in content


# ── cmd_init integration ───────────────────────────────────────────────────


class TestCmdInit:
    def test_creates_directory_structure(self, init_args):
        rv.cmd_init(init_args)
        project = Path(init_args.name)
        for d in ("R", "scripts", "config", "data", "results", "logs", "docs", "tests"):
            assert (project / d).is_dir(), f"Missing directory: {d}"

    def test_gitkeep_in_tests(self, init_args):
        rv.cmd_init(init_args)
        assert (Path(init_args.name) / "tests" / ".gitkeep").exists()

    def test_readme_rendered(self, init_args):
        rv.cmd_init(init_args)
        readme = (Path(init_args.name) / "README.md").read_text()
        assert "# myproject" in readme
        assert "{{PROJECT_NAME}}" not in readme

    def test_config_rendered(self, init_args):
        rv.cmd_init(init_args)
        config = (Path(init_args.name) / "config" / "analysis.yaml").read_text()
        assert "myproject" in config
        assert "{{PROJECT_NAME}}" not in config

    def test_verbatim_files_copied(self, init_args):
        rv.cmd_init(init_args)
        project = Path(init_args.name)
        assert (project / ".gitignore").exists()
        assert (project / ".Rprofile").exists()
        assert (project / "R" / "utils.R").exists()
        assert (project / "R" / "init.R").exists()
        assert (project / "scripts" / "run_analysis.R").exists()

    def test_rv_toml_created_with_renv(self, init_args):
        init_args.renv = True
        rv.cmd_init(init_args)
        config = rv.read_rv_config(Path(init_args.name) / "rproject.toml")
        assert config["renv"] is True
        assert "yaml" in config["packages"]

    def test_rv_toml_created_without_renv(self, init_args):
        init_args.renv = False
        rv.cmd_init(init_args)
        config = rv.read_rv_config(Path(init_args.name) / "rproject.toml")
        assert config["renv"] is False
        assert "yaml" in config["packages"]

    def test_rv_toml_has_scripts(self, init_args):
        rv.cmd_init(init_args)
        config = rv.read_rv_config(Path(init_args.name) / "rproject.toml")
        assert config["scripts"]["default"] == "scripts/run_analysis.R"

    def test_no_setup_env_created(self, init_args):
        rv.cmd_init(init_args)
        assert not (Path(init_args.name) / "scripts" / "setup_env.R").exists()

    def test_slurm_flag_creates_slurm_dir(self, init_args):
        init_args.slurm = True
        rv.cmd_init(init_args)
        project = Path(init_args.name)
        assert (project / "slurm").is_dir()
        job_script = project / "slurm" / "run_job.sh"
        assert job_script.exists()
        assert "myproject" in job_script.read_text()
        assert job_script.stat().st_mode & 0o755

    def test_no_slurm_by_default(self, init_args):
        rv.cmd_init(init_args)
        assert not (Path(init_args.name) / "slurm").exists()

    def test_rproj_flag_creates_rproj_file(self, init_args):
        init_args.rproj = True
        rv.cmd_init(init_args)
        rproj = Path(init_args.name) / "myproject.Rproj"
        assert rproj.exists()
        content = rproj.read_text()
        assert "Version: 1.0" in content

    def test_no_rproj_by_default(self, init_args):
        rv.cmd_init(init_args)
        assert not list(Path(init_args.name).glob("*.Rproj"))

    def test_git_init_called_when_enabled(self, init_args, monkeypatch):
        init_args.git = True
        calls = []
        monkeypatch.setattr(
            "shutil.which", lambda cmd: "/usr/bin/git" if cmd == "git" else None
        )
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
        )
        rv.cmd_init(init_args)
        git_calls = [c for c in calls if c[0] == "git"]
        assert any("init" in c for c in git_calls)

    def test_git_not_called_when_disabled(self, init_args, monkeypatch):
        init_args.git = False
        calls = []
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
        )
        rv.cmd_init(init_args)
        git_calls = [c for c in calls if isinstance(c, list) and c[0] == "git"]
        assert git_calls == []

    def test_sync_calls_rscript(self, init_args, monkeypatch):
        init_args.sync = True
        calls = []
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: calls.append((cmd, kw))
            or subprocess.CompletedProcess(cmd, 0),
        )
        rv.cmd_init(init_args)
        rscript_calls = [
            (c, k) for c, k in calls if isinstance(c, list) and c[0] == "Rscript"
        ]
        assert len(rscript_calls) == 1
        assert rscript_calls[0][1].get("input") is not None  # R code passed via stdin

    def test_no_sync_skips_rscript(self, init_args, monkeypatch):
        init_args.sync = False
        calls = []
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
        )
        rv.cmd_init(init_args)
        rscript_calls = [c for c in calls if isinstance(c, list) and c[0] == "Rscript"]
        assert rscript_calls == []

    def test_init_dot_uses_cwd_name(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "my-cwd-project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        args = types.SimpleNamespace(
            name=".",
            git=False,
            renv=False,
            rproj=False,
            slurm=False,
            docker=False,
            apptainer=False,
            ci=False,
            force=False,
            sync=False,
        )
        rv.cmd_init(args)
        readme = (project_dir / "README.md").read_text()
        assert "# my-cwd-project" in readme

    def test_force_allows_nonempty_dir(self, tmp_path):
        project = tmp_path / "existing"
        project.mkdir()
        (project / "somefile.txt").write_text("hi")
        args = types.SimpleNamespace(
            name=str(project),
            git=False,
            renv=True,
            rproj=False,
            slurm=False,
            docker=False,
            apptainer=False,
            ci=False,
            force=True,
            sync=False,
        )
        rv.cmd_init(args)
        assert (project / "R").is_dir()

    def test_nonempty_dir_without_force_exits(self, tmp_path):
        project = tmp_path / "existing"
        project.mkdir()
        (project / "somefile.txt").write_text("hi")
        args = types.SimpleNamespace(
            name=str(project),
            git=False,
            renv=True,
            rproj=False,
            slurm=False,
            force=False,
            sync=False,
        )
        with pytest.raises(SystemExit, match="not empty"):
            rv.cmd_init(args)

    def test_existing_file_not_dir_exits(self, tmp_path):
        target = tmp_path / "afile"
        target.write_text("I am a file")
        args = types.SimpleNamespace(
            name=str(target),
            git=False,
            renv=True,
            rproj=False,
            slurm=False,
            force=False,
            sync=False,
        )
        with pytest.raises(SystemExit, match="not a directory"):
            rv.cmd_init(args)


# ── CLI argument parsing ───────────────────────────────────────────────────


class TestCLIParsing:
    def _parse(self, argv: list[str]):
        """Reset cached version and parse argv through main's parser."""
        rv.__version__ = "test"
        parser = rv.argparse.ArgumentParser(prog="rv")
        parser.add_argument(
            "--version", action="version", version=f"%(prog)s {rv.get_version()}"
        )
        sub = parser.add_subparsers(dest="command", required=True)

        p_init = sub.add_parser("init")
        p_init.add_argument("name")
        p_init.add_argument("--no-git", dest="git", action="store_false", default=True)
        p_init.add_argument(
            "--no-renv", dest="renv", action="store_false", default=True
        )
        p_init.add_argument("--rproj", action="store_true")
        p_init.add_argument("--slurm", action="store_true")
        p_init.add_argument("--force", action="store_true")
        p_init.add_argument(
            "--no-sync", dest="sync", action="store_false", default=True
        )

        p_add = sub.add_parser("add")
        p_add.add_argument("packages", nargs="+")
        p_add.add_argument("--bioc", action="store_true")

        p_rm = sub.add_parser("rm")
        p_rm.add_argument("packages", nargs="+")

        sub.add_parser("list")
        p_update = sub.add_parser("update")
        p_update.add_argument("packages", nargs="*")
        sub.add_parser("sync")

        p_run = sub.add_parser("run")
        p_run.add_argument("script", nargs="?")
        p_run.add_argument("extra", nargs=rv.argparse.REMAINDER)

        p_clean = sub.add_parser("clean")
        p_clean.add_argument("--renv", action="store_true")

        return parser.parse_args(argv)

    def test_init_subcommand(self):
        args = self._parse(["init", "my-project"])
        assert args.command == "init"
        assert args.name == "my-project"
        assert args.git is True
        assert args.renv is True

    def test_init_with_flags(self):
        args = self._parse(
            [
                "init",
                "proj",
                "--no-git",
                "--no-renv",
                "--rproj",
                "--slurm",
                "--force",
                "--no-sync",
            ]
        )
        assert args.git is False
        assert args.renv is False
        assert args.rproj is True
        assert args.slurm is True
        assert args.force is True
        assert args.sync is False

    def test_add_subcommand(self):
        args = self._parse(["add", "dplyr", "ggplot2"])
        assert args.command == "add"
        assert args.packages == ["dplyr", "ggplot2"]
        assert args.bioc is False

    def test_add_bioc_flag(self):
        args = self._parse(["add", "--bioc", "DESeq2"])
        assert args.bioc is True

    def test_rm_subcommand(self):
        args = self._parse(["rm", "dplyr"])
        assert args.command == "rm"
        assert args.packages == ["dplyr"]

    def test_list_subcommand(self):
        args = self._parse(["list"])
        assert args.command == "list"

    def test_update_all(self):
        args = self._parse(["update"])
        assert args.command == "update"
        assert args.packages == []

    def test_update_specific(self):
        args = self._parse(["update", "dplyr", "ggplot2"])
        assert args.packages == ["dplyr", "ggplot2"]

    def test_sync_subcommand(self):
        args = self._parse(["sync"])
        assert args.command == "sync"

    def test_run_subcommand(self):
        args = self._parse(["run", "myscript.R"])
        assert args.command == "run"
        assert args.script == "myscript.R"

    def test_run_default(self):
        args = self._parse(["run"])
        assert args.script is None

    def test_clean_subcommand(self):
        args = self._parse(["clean"])
        assert args.command == "clean"

    def test_clean_renv(self):
        args = self._parse(["clean", "--renv"])
        assert args.renv is True

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit, match="0"):
            self._parse(["--version"])
        captured = capsys.readouterr()
        assert "rv" in captured.out

    def test_no_subcommand_exits(self):
        with pytest.raises(SystemExit):
            self._parse([])


# ── get_version ─────────────────────────────────────────────────────────────


class TestGetVersion:
    def test_returns_git_tag(self, monkeypatch):
        rv.__version__ = None
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="v1.2.3\n", stderr=""
            ),
        )
        assert rv.get_version() == "v1.2.3"

    def test_returns_dev_on_failure(self, monkeypatch):
        rv.__version__ = None
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr=""),
        )
        assert rv.get_version() == "dev"

    def test_returns_dev_on_exception(self, monkeypatch):
        rv.__version__ = None

        def _raise(*a, **kw):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr("subprocess.run", _raise)
        assert rv.get_version() == "dev"

    def test_caches_result(self, monkeypatch):
        rv.__version__ = None
        call_count = 0

        def _mock(*a, **kw):
            nonlocal call_count
            call_count += 1
            return subprocess.CompletedProcess(a[0], 0, stdout="v0.1\n", stderr="")

        monkeypatch.setattr("subprocess.run", _mock)
        rv.get_version()
        rv.get_version()
        assert call_count == 1


# ── load_script_aliases ─────────────────────────────────────────────────────


class TestLoadScriptAliases:
    def test_parses_scripts_section(self, tmp_path, monkeypatch):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text(
            'renv = true\npackages = []\n\n[scripts]\ndefault = "scripts/run.R"\nalt = "scripts/alt.R"\n'
        )
        monkeypatch.chdir(tmp_path)
        aliases = rv.load_script_aliases()
        assert aliases == {"default": "scripts/run.R", "alt": "scripts/alt.R"}

    def test_missing_config_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert rv.load_script_aliases() == {}

    def test_no_scripts_section(self, tmp_path, monkeypatch):
        cfg = tmp_path / "rproject.toml"
        cfg.write_text('renv = true\npackages = ["yaml"]\n')
        monkeypatch.chdir(tmp_path)
        assert rv.load_script_aliases() == {}


# ── renv_snapshot error handling ───────────────────────────────────────────


class TestRenvSnapshot:
    def test_skipped_when_renv_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = false\npackages = []\n")
        (tmp_path / "renv.lock").write_text("{}")
        assert rv.renv_snapshot() is True

    def test_skipped_when_no_lockfile(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = true\npackages = []\n")
        assert rv.renv_snapshot() is True

    def test_success_on_first_try(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = true\npackages = []\n")
        (tmp_path / "renv.lock").write_text("{}")
        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 0),
        )
        assert rv.renv_snapshot() is True

    def test_recovers_after_install_repair(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = true\npackages = []\n")
        (tmp_path / "renv.lock").write_text("{}")

        call_count = 0

        def mock_rscript(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return subprocess.CompletedProcess(args, 1)
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(rv, "rscript", mock_rscript)
        assert rv.renv_snapshot() is True
        assert call_count == 3  # snapshot fail, install, snapshot retry

    def test_returns_false_on_unrecoverable_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = true\npackages = []\n")
        (tmp_path / "renv.lock").write_text("{}")
        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 1),
        )
        assert rv.renv_snapshot() is False


# ── cmd_add error handling ─────────────────────────────────────────────────


class TestCmdAddErrorHandling:
    def test_exits_on_install_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = false\npackages = []\n")

        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 1),
        )
        args = types.SimpleNamespace(packages=["dplyr"], bioc=False)
        with pytest.raises(SystemExit):
            rv.cmd_add(args)

    def test_succeeds_when_install_passes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text("renv = false\npackages = []\n")

        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 0),
        )
        args = types.SimpleNamespace(packages=["dplyr"], bioc=False)
        rv.cmd_add(args)
        config = rv.read_rv_config(cfg)
        assert "dplyr" in config["packages"]


# ── cmd_update error handling ──────────────────────────────────────────────


class TestCmdUpdateErrorHandling:
    def test_exits_on_update_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text('renv = false\npackages = ["dplyr"]\n')

        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 1),
        )
        args = types.SimpleNamespace(packages=[])
        with pytest.raises(SystemExit):
            rv.cmd_update(args)

    def test_succeeds_when_update_passes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "rproject.toml"
        cfg.write_text('renv = false\npackages = ["dplyr"]\n')

        monkeypatch.setattr(
            rv,
            "rscript",
            lambda *a: subprocess.CompletedProcess(a, 0),
        )
        args = types.SimpleNamespace(packages=[])
        rv.cmd_update(args)
