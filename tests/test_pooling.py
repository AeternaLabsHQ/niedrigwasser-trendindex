from niedrigwasser.pooling import pooled_spells


def test_single_run():
    below = [False, True, True, True, False]
    assert pooled_spells(below) == [(1, 3)]


def test_gap_leq_5_merges():
    # Run 0-2, 5 Tage Luecke (3..7), Run 8-9 -> ein Ereignis von 0 bis 9
    below = [True] * 3 + [False] * 5 + [True] * 2
    assert pooled_spells(below, inter_event=5) == [(0, 10)]


def test_gap_gt_5_splits():
    below = [True] * 3 + [False] * 6 + [True] * 2
    assert pooled_spells(below, inter_event=5) == [(0, 3), (9, 2)]


def test_inter_event_3():
    below = [True] * 2 + [False] * 4 + [True] * 1
    assert pooled_spells(below, inter_event=3) == [(0, 2), (6, 1)]
    assert pooled_spells(below, inter_event=4) == [(0, 7)]


def test_chained_merging():
    # drei Runs mit je 2er-Luecken -> alles ein Ereignis
    below = [True, False, False, True, False, False, True]
    assert pooled_spells(below, inter_event=2) == [(0, 7)]


def test_empty_and_all_below():
    assert pooled_spells([False] * 10) == []
    assert pooled_spells([True] * 10) == [(0, 10)]
