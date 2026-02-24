from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from time_plot.units import scale_for_display


@dataclass(slots=True)
class SeriesData:
    source_name: str
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    x: np.ndarray
    y: np.ndarray
    x_display_prefix: str | None = None
    y_display_prefix: str | None = None

    def __post_init__(self) -> None:
        self.x = np.asarray(self.x, dtype=np.float64)
        self.y = np.asarray(self.y, dtype=np.float64)
        if self.x.shape != self.y.shape:
            msg = "x and y arrays must have the same shape"
            raise ValueError(msg)

    @property
    def x_axis_label(self) -> str:
        x_scaled, axis_label = self.x_display()
        del x_scaled
        return axis_label

    @property
    def y_axis_label(self) -> str:
        y_scaled, axis_label = self.y_display()
        del y_scaled
        return axis_label

    def x_display(self) -> tuple[np.ndarray, str]:
        scaled = scale_for_display(
            self.x,
            base_unit=self.x_unit,
            forced_prefix=self.x_display_prefix,
        )
        label = f"{self.x_label} ({scaled.display_unit})" if scaled.display_unit else self.x_label
        return scaled.scaled_values, label

    def y_display(self) -> tuple[np.ndarray, str]:
        scaled = scale_for_display(
            self.y,
            base_unit=self.y_unit,
            forced_prefix=self.y_display_prefix,
        )
        label = f"{self.y_label} ({scaled.display_unit})" if scaled.display_unit else self.y_label
        return scaled.scaled_values, label
