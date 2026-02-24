from __future__ import annotations

from pathlib import Path

from time_plot.sample_data import write_example_data_files


def test_write_example_data_files_creates_expected_csvs(tmp_path: Path) -> None:
    written = write_example_data_files(tmp_path)

    assert [path.name for path in written] == ["sine.csv", "cosine.csv"]

    sine_header = (tmp_path / "sine.csv").read_text(encoding="utf-8").splitlines()[0]
    cosine_header = (tmp_path / "cosine.csv").read_text(encoding="utf-8").splitlines()[0]
    assert sine_header == "time(ns),voltage(mv)"
    assert cosine_header == "time(ns),voltage(mv)"

    assert len((tmp_path / "sine.csv").read_text(encoding="utf-8").splitlines()) == 1001
    assert len((tmp_path / "cosine.csv").read_text(encoding="utf-8").splitlines()) == 801

