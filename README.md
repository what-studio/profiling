Profiling
=========

The profiling package is an interactive Python profiler.  It provides these
features:

1. An interactive TUI profiling statistics viewer.
1. Utilities for remote profiling.
1. Greenlet-aware CPU timer.
1. Supports both of Python 2.7 and Python 3.4.

Installation
------------

This project is under development yet.  So you should install it via GitHub
instead of PyPI:

```sh
$ pip install git+ssh://git@github.com/what-studio/profiling.git
```

Usage
-----

To profile a single program, simply run `profile` command:

```sh
$ python -m profiling profile your-program.py
```

Then an interactive viewer will be executed:

![](screenshots/your-program.png)

If your program uses greenlets, choose `greenlet` timer:

```sh
$ python -m profiling profile your-program.py --timer=greenlet
```

With `--dump` option, it saves the profiling result to a file.  You can browse
save result by `view` command.

```sh
$ python -m profiling profile your-program.py --dump=your-program.prf
$ python -m profiling view your-program.prf
```

You can start and stop a profiler by Python code:

```python
from profiling import Profiler
profiler = Profiler()
profiler.start()
your_program()
profiler.stop()
```

Licensing
---------

This project is opened under the [BSD 3-Clause] license.

[BSD 3-Clause]: http://opensource.org/licenses/BSD-3-Clause
