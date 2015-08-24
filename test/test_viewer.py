# -*- coding: utf-8 -*-
from profiling.viewer import fmt


def test_fmt():
    assert fmt.markup_percent(1.00) == ('danger', '100')
    assert fmt.markup_percent(0.80) == ('caution', '80.0')
    assert fmt.markup_percent(0.50) == ('warning', '50.0')
    assert fmt.markup_percent(0.20) == ('notice', '20.0')
    assert fmt.markup_percent(0.05) == (None, '5.00')
    assert fmt.markup_percent(0.00) == ('zero', '0.00')
    assert fmt.markup_percent(0.00, unit=True) == ('zero', '0.00%')
    assert fmt.markup_int(1.234) == (None, '1')
    assert fmt.markup_int(4.567) == (None, '5')
    assert fmt.markup_int(0) == ('zero', '0')
    assert fmt.markup_int_or_na(1.234) == (None, '1')
    assert fmt.markup_int_or_na(0) == ('zero', 'n/a')
    assert fmt.markup_time(0) == ('zero', '0')
    assert fmt.markup_time(0.123456) == ('msec', '123ms')
    assert fmt.markup_time(12.34567) == ('sec', '12.3sec')


def test_format_int():
    assert fmt.format_int(0) == '0'
    assert fmt.format_int(123) == '123'
    assert fmt.format_int(12345) == '12.3k'
    assert fmt.format_int(-12345) == '-12.3k'
    assert fmt.format_int(99999999) == '100.0M'
    assert fmt.format_int(-99999999) == '-100.0M'
    assert fmt.format_int(999999999) == '1.0G'
    assert fmt.format_int(-999999999) == '-1.0G'
    assert fmt.format_int(1e255) == 'o/f'
    assert fmt.format_int(-1e255) == 'u/f'


def test_format_int_or_na():
    assert fmt.format_int_or_na(0) == 'n/a'
    assert fmt.format_int_or_na(12345) == '12.3k'


def test_format_time():
    assert fmt.format_time(0) == '0'
    assert fmt.format_time(0.000001) == '1us'
    assert fmt.format_time(0.000123) == '123us'
    assert fmt.format_time(0.012345) == '12ms'
    assert fmt.format_time(0.123456) == '123ms'
    assert fmt.format_time(1.234567) == '1.2sec'
    assert fmt.format_time(12.34567) == '12.3sec'
    assert fmt.format_time(123.4567) == '2min3s'
    assert fmt.format_time(6120.000) == '102min'


def test_format_percent():
    assert fmt.format_percent(1) == '100'
    assert fmt.format_percent(0.999999) == '100'
    assert fmt.format_percent(0.9999) == '100'
    assert fmt.format_percent(0.988) == '98.8'
