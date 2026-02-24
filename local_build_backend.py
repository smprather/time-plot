from __future__ import annotations

import base64
import csv
import hashlib
import io
from pathlib import Path
import tarfile
import tomllib
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parent


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    project = _project_metadata()
    dist = _wheel_dist_name(project["name"])
    version = project["version"]
    wheel_name = f"{dist}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    wheel_path.parent.mkdir(parents=True, exist_ok=True)

    dist_info = f"{dist}-{version}.dist-info"
    records: list[tuple[str, bytes]] = []

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path in _wheel_file_list():
            data = (ROOT / rel_path).read_bytes()
            arcname = rel_path.as_posix()
            zf.writestr(arcname, data)
            records.append((arcname, data))

        metadata_path = f"{dist_info}/METADATA"
        metadata_bytes = _metadata_text(project).encode("utf-8")
        zf.writestr(metadata_path, metadata_bytes)
        records.append((metadata_path, metadata_bytes))

        wheel_meta_path = f"{dist_info}/WHEEL"
        wheel_meta_bytes = (
            "Wheel-Version: 1.0\n"
            "Generator: local_build_backend\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode("utf-8")
        zf.writestr(wheel_meta_path, wheel_meta_bytes)
        records.append((wheel_meta_path, wheel_meta_bytes))

        scripts = project.get("scripts", {})
        if scripts:
            entry_points_path = f"{dist_info}/entry_points.txt"
            entry_points_bytes = _entry_points_text(scripts).encode("utf-8")
            zf.writestr(entry_points_path, entry_points_bytes)
            records.append((entry_points_path, entry_points_bytes))

        record_path = f"{dist_info}/RECORD"
        record_bytes = _record_csv(records, record_path).encode("utf-8")
        zf.writestr(record_path, record_bytes)

    return wheel_name


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    del config_settings
    project = _project_metadata()
    name = _sdist_dist_name(project["name"])
    version = project["version"]
    sdist_name = f"{name}-{version}.tar.gz"
    sdist_path = Path(sdist_directory) / sdist_name
    sdist_path.parent.mkdir(parents=True, exist_ok=True)
    root_prefix = f"{name}-{version}"

    with tarfile.open(sdist_path, "w:gz") as tf:
        for rel_path in _sdist_file_list():
            abs_path = ROOT / rel_path
            arcname = f"{root_prefix}/{rel_path.as_posix()}"
            tf.add(abs_path, arcname=arcname, recursive=False)

        pkg_info = _metadata_text(project).encode("utf-8")
        tarinfo = tarfile.TarInfo(name=f"{root_prefix}/PKG-INFO")
        tarinfo.size = len(pkg_info)
        tarinfo.mode = 0o644
        tf.addfile(tarinfo, io.BytesIO(pkg_info))

    return sdist_name


def get_requires_for_build_sdist(config_settings: dict[str, Any] | None = None) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_wheel(config_settings: dict[str, Any] | None = None) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_editable(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    del config_settings
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    del config_settings
    project = _project_metadata()
    dist = _wheel_dist_name(project["name"])
    version = project["version"]
    dist_info_dir = Path(metadata_directory) / f"{dist}-{version}.dist-info"
    dist_info_dir.mkdir(parents=True, exist_ok=True)
    (dist_info_dir / "METADATA").write_text(_metadata_text(project), encoding="utf-8")
    (dist_info_dir / "WHEEL").write_text(
        "Wheel-Version: 1.0\n"
        "Generator: local_build_backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n",
        encoding="utf-8",
    )
    scripts = project.get("scripts", {})
    if scripts:
        (dist_info_dir / "entry_points.txt").write_text(
            _entry_points_text(scripts),
            encoding="utf-8",
        )
    return dist_info_dir.name


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    project = _project_metadata()
    dist = _wheel_dist_name(project["name"])
    version = project["version"]
    wheel_name = f"{dist}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    wheel_path.parent.mkdir(parents=True, exist_ok=True)

    dist_info = f"{dist}-{version}.dist-info"
    records: list[tuple[str, bytes]] = []

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        pth_name = f"{dist}.pth"
        pth_bytes = (str(ROOT) + "\n").encode("utf-8")
        zf.writestr(pth_name, pth_bytes)
        records.append((pth_name, pth_bytes))

        metadata_path = f"{dist_info}/METADATA"
        metadata_bytes = _metadata_text(project).encode("utf-8")
        zf.writestr(metadata_path, metadata_bytes)
        records.append((metadata_path, metadata_bytes))

        wheel_meta_path = f"{dist_info}/WHEEL"
        wheel_meta_bytes = (
            "Wheel-Version: 1.0\n"
            "Generator: local_build_backend\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode("utf-8")
        zf.writestr(wheel_meta_path, wheel_meta_bytes)
        records.append((wheel_meta_path, wheel_meta_bytes))

        scripts = project.get("scripts", {})
        if scripts:
            entry_points_path = f"{dist_info}/entry_points.txt"
            entry_points_bytes = _entry_points_text(scripts).encode("utf-8")
            zf.writestr(entry_points_path, entry_points_bytes)
            records.append((entry_points_path, entry_points_bytes))

        record_path = f"{dist_info}/RECORD"
        record_bytes = _record_csv(records, record_path).encode("utf-8")
        zf.writestr(record_path, record_bytes)

    return wheel_name


def _project_metadata() -> dict[str, Any]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = dict(pyproject["project"])
    project["dependencies"] = list(project.get("dependencies", []))
    project["scripts"] = dict(project.get("scripts", {}))
    return project


def _metadata_text(project: dict[str, Any]) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
    ]
    if description := project.get("description"):
        lines.append(f"Summary: {description}")
    if requires_python := project.get("requires-python"):
        lines.append(f"Requires-Python: {requires_python}")
    for dependency in project.get("dependencies", []):
        lines.append(f"Requires-Dist: {dependency}")
    return "\n".join(lines) + "\n"


def _entry_points_text(scripts: dict[str, str]) -> str:
    lines = ["[console_scripts]"]
    for name, target in sorted(scripts.items()):
        lines.append(f"{name} = {target}")
    return "\n".join(lines) + "\n"


def _record_csv(records: list[tuple[str, bytes]], record_path: str) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for path, data in records:
        digest = hashlib.sha256(data).digest()
        hash_b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        writer.writerow([path, f"sha256={hash_b64}", str(len(data))])
    writer.writerow([record_path, "", ""])
    return out.getvalue()


def _wheel_file_list() -> list[Path]:
    files: list[Path] = []
    files.extend(_iter_files(Path("time_plot")))
    files.extend(_iter_files(Path("plugins")))
    files.extend(_iter_files(Path("sample_data")))
    return sorted(files)


def _sdist_file_list() -> list[Path]:
    files = [
        Path("pyproject.toml"),
        Path("README.md"),
        Path("AGENTS.md"),
        Path("main.py"),
        Path("local_build_backend.py"),
        *_wheel_file_list(),
    ]
    deduped = {path.as_posix(): path for path in files}
    return [deduped[key] for key in sorted(deduped)]


def _iter_files(root_rel: Path) -> list[Path]:
    root = ROOT / root_rel
    if not root.exists():
        return []
    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        results.append(path.relative_to(ROOT))
    return results


def _wheel_dist_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "." else "_" for ch in name)


def _sdist_dist_name(name: str) -> str:
    return name.replace(" ", "-").replace("/", "-")
