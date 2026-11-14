from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from statistics import mean
from time import perf_counter


@dataclass(frozen=True)
class BenchmarkStats:
    samples_s: tuple[float, ...]

    @property
    def mean_s(self) -> float:
        return mean(self.samples_s)

    @property
    def median_s(self) -> float:
        ordered = sorted(self.samples_s)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2

    @property
    def min_s(self) -> float:
        return min(self.samples_s)

    @property
    def max_s(self) -> float:
        return max(self.samples_s)

    def percentile_s(self, percentile: float) -> float:
        if not self.samples_s:
            raise ValueError('Can not calculate percentile for empty benchmark')
        if not 0 < percentile <= 100:
            raise ValueError(f'Percentile should be in (0, 100], got {percentile}')

        ordered = sorted(self.samples_s)
        # Nearest-rank percentile: for 10 samples p95 points to the 10th sample.
        rank = max(1, ceil(percentile / 100 * len(ordered)))
        return ordered[rank - 1]

    @property
    def p95_s(self) -> float:
        return self.percentile_s(95)

    def describe(self) -> str:
        return (
            f'n={len(self.samples_s)} '
            f'min={self.min_s:.3f}s '
            f'median={self.median_s:.3f}s '
            f'mean={self.mean_s:.3f}s '
            f'p95={self.p95_s:.3f}s '
            f'max={self.max_s:.3f}s'
        )


async def measure_async(
    operation: Callable[[], Awaitable],
    iterations: int,
    warmup: int = 1,
) -> BenchmarkStats:
    if iterations < 1:
        raise ValueError(f'Iterations should be positive, got {iterations}')
    if warmup < 0:
        raise ValueError(f'Warmup should not be negative, got {warmup}')

    for _ in range(warmup):
        await operation()

    samples = []
    for _ in range(iterations):
        started_at = perf_counter()
        await operation()
        samples.append(perf_counter() - started_at)

    return BenchmarkStats(tuple(samples))
