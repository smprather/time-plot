import math


# ---------------------------------------------------------------------------
# Helpers for auto-sizing
# ---------------------------------------------------------------------------

def _nice_ceil(x):
    """Round x up to the nearest value in the {1, 2, 5} × 10^k series."""
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    norm = x / (10.0 ** exp)
    # Small epsilon guards against floating-point values like 1.9999999 → 2.
    if norm <= 1.0 + 1e-9:
        nice = 1.0
    elif norm <= 2.0 + 1e-9:
        nice = 2.0
    elif norm <= 5.0 + 1e-9:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10.0 ** exp)


def _next_odd(n):
    n = int(math.ceil(n))
    return n if n % 2 == 1 else n + 1


# ---------------------------------------------------------------------------


class Stats:
    def __init__(self, data_set, sum_=None):
        if sum_ is None:
            sum_ = sum(data_set)
        n = len(data_set)
        self.mean = sum_ / n
        sum_sq = 0.0
        sum_sq_high = self.mean ** 2.0
        sum_sq_low = self.mean ** 2.0
        x_gt_mean_count = 1
        x_lt_mean_count = 1
        for x in data_set:
            d = (x - self.mean) ** 2.0
            sum_sq += d
            if x >= self.mean:
                sum_sq_high += 2.0 * d
                x_gt_mean_count += 2
            else:
                sum_sq_low += 2.0 * d
                x_lt_mean_count += 2
        self.sigma = 0.0 if n == 1 else (sum_sq / (n - 1)) ** 0.5
        self.sigma_high = 0.0 if x_gt_mean_count == 1 else (sum_sq_high / (x_gt_mean_count - 1)) ** 0.5
        self.sigma_low = 0.0 if x_lt_mean_count == 1 else (sum_sq_low / (x_lt_mean_count - 1)) ** 0.5


class DataSet(list):
    """A list of floats with a label, units, and pre-computed statistics."""

    def __init__(self, data_set, label="", units="", scale=1.0):
        super().__init__()
        self.label = label
        self.units = units
        total = 0.0
        for x in data_set:
            x = float(x)
            if not math.isfinite(x) or math.isnan(x):
                raise ValueError("Error: Infinity or NaN in dataset")
            temp = x * scale
            total += temp
            self.append(temp)
        self._recalc_stats(total)

    def _recalc_stats(self, total=None):
        if total is None:
            total = sum(self)
        s = Stats(self, total)
        self.mean = s.mean
        self.sigma = s.sigma
        self.sigma_high = s.sigma_high
        self.sigma_low = s.sigma_low


def _pad_and_justify(s, width, justify):
    j = justify[0].lower()
    if j == "l":
        return s.ljust(width)
    elif j == "r":
        return s.rjust(width)
    else:
        return s.center(width)


class Histogram:
    def __init__(self, num_buckets=15, bucket_size=10, middle_value=0.0, max_bar_height=20):
        self.num_buckets = num_buckets
        self.bucket_size = float(bucket_size)
        self.middle_value = float(middle_value)
        self.max_bar_height = max_bar_height
        self.data_sets = []
        self.bucket_sets = None
        self._min_edge = None
        self._max_edge_of_min_bucket = None
        self._min_edge_of_max_bucket = None

    @staticmethod
    def snap_to(value, ref_value, interval):
        return round((value - ref_value) / interval) * interval + ref_value

    @staticmethod
    def read_data_file(file_name, columns=None):
        """Read whitespace-delimited data. Returns one list per column (1-based indices)."""
        if columns is None:
            columns = [1]
        data_sets = [[] for _ in columns]
        with open(file_name) as f:
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                for i, col in enumerate(columns):
                    if col - 1 < len(parts):
                        data_sets[i].append(float(parts[col - 1]))
        return data_sets

    @staticmethod
    def to_SI(f, decimal_places=3, degree=None):
        if f is None:
            return "NA"
        prefixes = [" ", "k", "M", "G", "T", "P", "E", "Z", "Y", "y", "x", "a", "f", "p", "n", "u", "m"]
        if degree is None:
            degree = 0 if abs(f) < 1e-18 else math.floor(math.log10(abs(f)) / 3)
        value = round(f * (1000.0 ** (-1.0 * degree)), 9)
        return f"{value:.{decimal_places}f}" + prefixes[degree]

    @staticmethod
    def get_degree(f):
        return 0 if abs(f) < 1e-18 else round(math.log10(abs(f)))

    @staticmethod
    def get_SI_degree(f):
        return 0 if abs(f) < 1e-18 else math.floor((math.log10(abs(f)) + 1.0) / 3.0)

    @staticmethod
    def auto_size(data, min_buckets=21, bucket_size=None, middle_value=None, trim_empty_edges=True):
        """Derive (bucket_size, num_buckets, middle_value) from *data*.

        Uses the 10th–90th percentile range so that extreme outliers never
        inflate the bucket width or count — they simply land in the ±Inf edge
        buckets.  Pass *bucket_size* or *middle_value* to pin those values
        while still letting the others be derived automatically.

        When *trim_empty_edges* is True (default) and *middle_value* was not
        explicitly supplied, the bucket window is shifted so that no interior
        buckets are wasted as empty leading/trailing bins adjacent to the ±Inf
        overflow buckets.  Symmetric empty padding (data centred with extra
        buckets added to meet *min_buckets*) is left unchanged.
        """
        n = len(data)
        if n == 0:
            return (bucket_size or 1.0), min_buckets, (middle_value or 0.0)

        _middle_value_explicit = middle_value is not None

        sd = sorted(data)

        def pct(p):
            idx = (n - 1) * p / 100.0
            lo = int(idx)
            hi = min(lo + 1, n - 1)
            return sd[lo] + (idx - lo) * (sd[hi] - sd[lo])

        median_val = pct(50)

        # Use the 10th–90th range as a robust spread estimate; fall back to
        # wider percentiles and finally to the full range if data is very tight.
        bulk_range = pct(90) - pct(10)
        if bulk_range == 0:
            bulk_range = pct(95) - pct(5)
        if bulk_range == 0:
            bulk_range = sd[-1] - sd[0]

        if bucket_size is None:
            bucket_size = 1.0 if bulk_range == 0 else _nice_ceil(bulk_range / min_buckets)

        if middle_value is None:
            if bulk_range == 0:
                middle_value = float(sd[0])
            else:
                # Snap so that bucket EDGES land on clean multiples of bucket_size.
                # Edges are at middle_value ± k*bucket_size ± bucket_size/2, so we
                # need middle_value ≡ bucket_size/2 (mod bucket_size).
                middle_value = (
                    round((median_val - bucket_size / 2.0) / bucket_size) * bucket_size
                    + bucket_size / 2.0
                )

        if bulk_range == 0:
            num_buckets = 1
        else:
            n_interior = math.ceil(bulk_range / bucket_size)
            # +4 = 2 overflow edge buckets + 2 cushion so the bulk sits
            # comfortably inside the interior buckets.
            num_buckets = max(min_buckets, _next_odd(n_interior + 4))

        # Shift the window to eliminate asymmetric empty edge buckets.
        # Example: all-positive data centred on the median ends up with many
        # empty interior buckets on the negative side; shift right so those
        # collapse into the -Inf overflow bin, freeing buckets for the tail.
        # Skip when middle_value was explicit, or when data is a single point.
        if trim_empty_edges and not _middle_value_explicit and bulk_range != 0:
            _min_edge = middle_value - bucket_size / 2.0 - (num_buckets - 1) / 2.0 * bucket_size
            _first_interior_lo = _min_edge + bucket_size
            _last_interior_hi = _min_edge + (num_buckets - 1) * bucket_size

            leading = min(
                num_buckets - 2,
                max(0, math.floor((sd[0] - _first_interior_lo) / bucket_size)),
            )
            trailing = min(
                num_buckets - 2,
                max(0, math.floor((_last_interior_hi - sd[-1]) / bucket_size)),
            )

            # Symmetric empties = data centred with min_buckets padding; leave alone.
            if leading != trailing:
                middle_value += (leading - trailing) * bucket_size

        return bucket_size, num_buckets, middle_value

    def reduce_num_buckets_till_n_percent_in_edge(self, n, reduce_per_iter=2, min_buckets=3):
        n /= 100.0
        self.bucketize()
        print(".", end="", flush=True)
        while True:
            max_edge_pct = max(
                max(bs[0] / len(ds), bs[-1] / len(ds))
                for bs, ds in zip(self.bucket_sets, self.data_sets)
            )
            if max_edge_pct > n:
                break
            self.num_buckets -= reduce_per_iter
            if self.num_buckets < min_buckets:
                self.num_buckets = min_buckets
                break
            self.bucketize()
            print(".", end="", flush=True)

    def increase_num_buckets_till_n_percent_in_edge(self, n, increase_per_iter=2, max_buckets=30, print_dots=True):
        n /= 100.0
        orig_num_buckets = self.num_buckets
        self.bucketize()
        if print_dots:
            print(".", end="", flush=True)
        while True:
            max_edge_pct = 0.0
            max_edge_count = 0
            for bs, ds in zip(self.bucket_sets, self.data_sets):
                max_edge_pct = max(max_edge_pct, bs[0] / len(ds), bs[-1] / len(ds))
                max_edge_count = max(max_edge_count, bs[0], bs[-1])
            if max_edge_pct < n:
                if max_edge_count == 0 and self.num_buckets > orig_num_buckets:
                    self.num_buckets -= increase_per_iter
                break
            self.num_buckets += increase_per_iter
            if self.num_buckets > max_buckets:
                self.num_buckets = max_buckets
                break
            self.bucketize()
            if print_dots:
                print(".", end="", flush=True)

    def bucketize(self):
        self.bucket_sets = [[0] * self.num_buckets for _ in self.data_sets]
        self._min_edge = (
            self.middle_value
            - (self.bucket_size / 2.0)
            - ((self.num_buckets - 1) / 2) * self.bucket_size
        )
        self._max_edge_of_min_bucket = self._min_edge + self.bucket_size
        self._min_edge_of_max_bucket = self._min_edge + (self.num_buckets - 1) * self.bucket_size
        for i, ds in enumerate(self.data_sets):
            for x in ds:
                if x < self._max_edge_of_min_bucket:
                    self.bucket_sets[i][0] += 1
                elif x > self._min_edge_of_max_bucket:
                    self.bucket_sets[i][-1] += 1
                else:
                    self.bucket_sets[i][int((x - self._min_edge) / self.bucket_size)] += 1

    def gen_histogram(self):
        self.bucketize()
        num_cols = 3 + 3 * len(self.data_sets)
        out_cols = [[None] * self.num_buckets for _ in range(num_cols)]
        col_max_widths = [0] * num_cols

        for i in range(self.num_buckets):
            out_cols[1][i] = "->"

        def bucket_edge_format(x):
            # Round to the number of decimal places implied by bucket_size:
            # bucket_size=10→0 decimals, 1→0, 0.1→1, 0.005→3, etc.
            dp = max(0, -math.floor(math.log10(self.bucket_size))) if self.bucket_size > 0 else 0
            v = round(x, dp)
            return int(v) if dp == 0 else v

        # First row: -Inf -> <upper edge of first bucket>
        out_cols[0][0] = "-Inf"
        col_max_widths[0] = 4
        s = str(bucket_edge_format(self._max_edge_of_min_bucket))
        out_cols[2][0] = s
        col_max_widths[2] = len(s)

        # Middle rows
        last_edge = self._max_edge_of_min_bucket
        for i in range(self.num_buckets - 2):
            next_edge = last_edge + self.bucket_size
            s = str(bucket_edge_format(last_edge))
            out_cols[0][i + 1] = s
            col_max_widths[0] = max(col_max_widths[0], len(s))
            s = str(bucket_edge_format(next_edge))
            out_cols[2][i + 1] = s
            col_max_widths[2] = max(col_max_widths[2], len(s))
            last_edge = next_edge

        # Last row: <lower edge of last bucket> -> +Inf
        s = str(bucket_edge_format(self._min_edge_of_max_bucket))
        out_cols[0][-1] = s
        col_max_widths[0] = max(col_max_widths[0], len(s))
        out_cols[2][-1] = "+Inf"
        col_max_widths[2] = max(col_max_widths[2], 4)

        for i, bucket_set in enumerate(self.bucket_sets):
            max_count = max(bucket_set) if bucket_set else 0
            one_star = max_count / self.max_bar_height if max_count > 0 else 1.0
            ds_len = len(self.data_sets[i])
            for j, count in enumerate(bucket_set):
                col0 = 3 + 3 * i
                col1 = col0 + 1
                col2 = col1 + 1

                s = str(count)
                out_cols[col0][j] = s
                col_max_widths[col0] = max(col_max_widths[col0], len(s))

                pct = round((count / ds_len) * 100.0, 1)
                s = f"{pct}%"
                out_cols[col1][j] = s
                col_max_widths[col1] = max(col_max_widths[col1], len(s))

                num_stars = max(0, round(count / one_star - 0.5 + 0.00001))
                s = "*" * num_stars
                out_cols[col2][j] = s
                col_max_widths[col2] = max(col_max_widths[col2], len(s))

        lines = []
        for i in range(self.num_buckets):
            line = ""
            for j, col in enumerate(out_cols):
                justify = "right" if j < 3 else ["right", "right", "left"][(j - 3) % 3]
                cell = col[i] if col[i] is not None else ""
                line += _pad_and_justify(cell, col_max_widths[j], justify) + " "
            lines.append(line.rstrip())
        return "\n".join(lines) + "\n"

    def __lshift__(self, data_set):
        self.data_sets.append(data_set)
        return self

    def global_min(self):
        return min(min(ds) for ds in self.data_sets)

    def global_max(self):
        return max(max(ds) for ds in self.data_sets)
