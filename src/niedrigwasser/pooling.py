from __future__ import annotations


def pooled_spells(below: list[bool], inter_event: int = 5) -> list[tuple[int, int]]:
    """Inter-Event-Pooling: Runs, getrennt durch <= inter_event Tage ueber
    Schwelle, werden zu einem Ereignis zusammengefasst. Rueckgabe
    (start_index, spannweite) je Ereignis; Spannweite inkl. ueberbrueckter Tage."""
    runs: list[tuple[int, int]] = []  # (start, ende_exklusiv) roher Runs
    start: int | None = None
    for i, b in enumerate(below):
        if b and start is None:
            start = i
        elif not b and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(below)))

    if not runs:
        return []

    pooled: list[tuple[int, int]] = [runs[0]]
    for s, e in runs[1:]:
        ps, pe = pooled[-1]
        if s - pe <= inter_event:
            pooled[-1] = (ps, e)
        else:
            pooled.append((s, e))
    return [(s, e - s) for s, e in pooled]
