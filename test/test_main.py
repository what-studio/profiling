# -*- coding: utf-8 -*-
import profiling.__main__ as m


def test_module_param_type():
    t = m.Module()
    # timeit
    filename, code, globals_ = t.convert('timeit', None, None)
    assert filename.endswith('timeit.py')
    assert code.co_filename.endswith('timeit.py')
    assert globals_['__name__'] == '__main__'
    assert globals_['__file__'].endswith('timeit.py')
    assert globals_['__package__'] == ''
    # profiling.__main__
    filename, code, globals_ = t.convert('profiling', None, None)
    assert filename.endswith('profiling/__main__.py')
    assert code.co_filename.endswith('profiling/__main__.py')
    assert globals_['__name__'] == '__main__'
    assert globals_['__file__'].endswith('profiling/__main__.py')
    assert globals_['__package__'] == 'profiling'
