"""N scans a day -> the hours (local time) a scheduler should fire them."""


def scan_hours(n: int, start: int = 8, end: int = 20) -> list[int]:
    if n < 1:
        raise ValueError("scans_per_day must be >= 1")
    if n == 1:
        return [start]
    step = (end - start) / (n - 1)
    return [round(start + i * step) for i in range(n)]
