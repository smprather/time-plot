from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from time_plot.sample_data import write_example_data_files


def main() -> None:
    output_dir = REPO_ROOT / "sample_data"
    for path in write_example_data_files(output_dir):
        print(f"Wrote example CSV: {path}")


if __name__ == "__main__":
    main()
