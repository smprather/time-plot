from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class SeriesData:
    source_name: str
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    x: np.ndarray
    y: np.ndarray

    def __post_init__(self) -> None:
        self.x = np.asarray(self.x, dtype=np.float64)
        self.y = np.asarray(self.y, dtype=np.float64)
        if self.x.shape != self.y.shape:
            msg = "x and y arrays must have the same shape"
            raise ValueError(msg)

    @property
    def x_axis_label(self) -> str:
        return f"{self.x_label} ({self.x_unit})" if self.x_unit else self.x_label

    @property
    def y_axis_label(self) -> str:
        return f"{self.y_label} ({self.y_unit})" if self.y_unit else self.y_label

