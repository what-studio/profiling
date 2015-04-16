Profiling
=========

The profiling package is an interactive Python profiler.  It is inspired from
[Unity 3D] profiler.  This package provides these features:

- Profiling statistics keep the frame stack.
- An interactive TUI profiling statistics viewer.
- Utilities for remote profiling.
- Thread or greenlet aware CPU timer.
- Supports Python 2.7, 3.2, 3.3 and 3.4.

[![Build Status]
(https://travis-ci.org/what-studio/profiling.svg?branch=master)]
(https://travis-ci.org/what-studio/profiling)
[![Coverage Status]
(https://coveralls.io/repos/what-studio/profiling/badge.svg?branch=master)]
(https://coveralls.io/r/what-studio/profiling)

[Unity 3D]: http://unity3d.com/

Installation
------------

This project is still under development, so you should install it via GitHub
instead of PyPI:

```sh
pip install git+https://github.com/what-studio/profiling.git
```

Profiling
---------

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

With `--dump` option, it saves the profiling result to a file.  You can
browse the saved result by using the `view` command:

```sh
$ python -m profiling profile your-program.py --dump=your-program.prf
$ python -m profiling view your-program.prf
```

Live-profiling
--------------

If your program has a long life time like a web server, profiling result
at the end of program doesn't help you.  You will need a continuous profiler.
It works via `live-profile` command:

```sh
$ python -m profiling live-profile webserver.py
```

See a demo:

[![asciicast](https://asciinema.org/a/12318.png)](https://asciinema.org/a/12318)

There's a live-profiling server also.  The server doesn't profile the
program at ordinary times.  But when a client connects to the server, it
runs profiler and reports to the all connected clients.  Start a server
with `remote-profile` command:

```sh
$ python -m profiling remote-profile webserver.py --bind 127.0.0.1:8912
```

Then run a client with `view` command:

```sh
$ python -m profiling view 127.0.0.1:8912
```

Profiling from code
-------------------

You can also profile your program by ``profiling.Profiler`` directly:

```python
from profiling import Profiler
from profiling.viewer import StatisticsViewer

# profile your program.
profiler = Profiler()
profiler.start()
...  # run your program.
profiler.stop()

# view statistics.
viewer = StatisticsViewer()
viewer.set_stats(profiler.stats)
loop = viewer.loop()
loop.run()
```

Viewer key commands
-------------------

- <tt>q</tt> - Quit.
- <tt>space</tt> - Pause/Resume.
- <tt>↑</tt> and <tt>↓</tt> - Navigate frames.
- <tt>→</tt> - Expand the frame.
- <tt>←</tt> - Fold the frame.
- <tt>></tt> - Go to the hotspot.
- <tt>esc</tt> - Defocus.
- <tt>[</tt> and <tt>]</tt> - Change sorting column.

Licensing
---------

This project is licensed under the [BSD 3-Clause] license.

[BSD 3-Clause]: http://opensource.org/licenses/BSD-3-Clause
