# -*- coding: utf-8 -*-
from profiling.viewer import fmt


def test_fmt():
    assert fmt.markup_percent(1.00) == ('danger', '100%')
    assert fmt.markup_percent(0.80) == ('caution', '80.0%')
    assert fmt.markup_percent(0.50) == ('warning', '50.0%')
    assert fmt.markup_percent(0.20) == ('notice', '20.0%')
    assert fmt.markup_percent(0.05) == (None, '5.00%')
    assert fmt.markup_percent(0.00) == ('zero', '0.00%')
    assert fmt.markup_int(1.234) == (None, '1')
    assert fmt.markup_int(4.567) == (None, '5')
    assert fmt.markup_int(0) == ('zero', '0')
    assert fmt.markup_int_or_na(1.234) == (None, '1')
    assert fmt.markup_int_or_na(0) == ('zero', 'n/a')
    assert fmt.markup_time(0) == ('zero', '0')
    assert fmt.markup_time(0.123456) == ('usec', '123.456')
    assert fmt.markup_time(12.34567) == ('sec', '12.35s')
