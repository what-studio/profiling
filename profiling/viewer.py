# -*- coding: utf-8 -*-
"""
   profiling.viewer
   ~~~~~~~~~~~~~~~~

   A text user interface application which inspects statistics.  To run it
   easily do:

   .. sourcecode:: console

      $ profiling view SOURCE

   ::

      viewer = StatisticsViewer()
      loop = viewer.loop()
      loop.run()

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from collections import deque

import urwid
from urwid import connect_signal as on

from profiling import sortkeys
from profiling.stats import FlatFrozenStatistics


__all__ = ['StatisticsTable', 'StatisticsViewer', 'fmt',
           'bind_vim_keys', 'bind_game_keys']


NESTED = 0
FLAT = 1


def get_func(f):
    if isinstance(f, staticmethod):
        return f.__func__
    return f


class Formatter(object):

    def _markup(get_string, get_attr=None):
        get_string = get_func(get_string)
        get_attr = get_func(get_attr)
        @staticmethod
        def markup(*args, **kwargs):
            string = get_string(*args, **kwargs)
            if get_attr is None:
                return string
            attr = get_attr(*args, **kwargs)
            return (attr, string)
        return markup

    _numeric = {'align': 'right', 'wrap': 'clip'}

    def _make_text(get_markup, **text_kwargs):
        get_markup = get_func(get_markup)
        @staticmethod
        def make_text(*args, **kwargs):
            markup = get_markup(*args, **kwargs)
            return urwid.Text(markup, **text_kwargs)
        return make_text

    # percent

    @staticmethod
    def format_percent(ratio, denom=1, unit=False):
        # width: 4~5 (with unit)
        # examples:
        # 0.01: 1.00%
        # 0.1: 10.0%
        # 1: 100%
        try:
            ratio /= float(denom)
        except ZeroDivisionError:
            ratio = 0
        if round(ratio, 2) >= 1:
            precision = 0
        elif round(ratio, 2) >= 0.1:
            precision = 1
        else:
            precision = 2
        string = ('{:.' + str(precision) + 'f}').format(ratio * 100)
        if unit:
            return string + '%'
        else:
            return string

    @staticmethod
    def attr_ratio(ratio, denom=1, unit=False):
        try:
            ratio /= float(denom)
        except ZeroDivisionError:
            ratio = 0
        if ratio > 0.9:
            return 'danger'
        elif ratio > 0.7:
            return 'caution'
        elif ratio > 0.3:
            return 'warning'
        elif ratio > 0.1:
            return 'notice'
        elif ratio <= 0:
            return 'zero'

    markup_percent = _markup(format_percent, attr_ratio)
    make_percent_text = _make_text(markup_percent, **_numeric)

    # int

    @staticmethod
    def format_int(num, units='kMGTPEZY'):
        # width: 1~6
        # examples:
        # 0: 0
        # 1: 1
        # 10: 10
        # 100: 100
        # 1000: 1.0K
        # 10000: 10.0K
        # 100000: 100.0K
        # 1000000: 1.0M
        # -10: -11
        unit = None
        unit_iter = iter(units)
        while abs(round(num, 1)) >= 1e3:
            num /= 1e3
            try:
                unit = next(unit_iter)
            except StopIteration:
                # overflow or underflow.
                return 'o/f' if num > 0 else 'u/f'
        if unit is None:
            return '{:.0f}'.format(num)
        else:
            return '{:.1f}{}'.format(num, unit)

    @staticmethod
    def attr_int(num):
        return None if num else 'zero'

    markup_int = _markup(format_int, attr_int)
    make_int_text = _make_text(markup_int, **_numeric)

    # int or n/a

    @staticmethod
    def format_int_or_na(num):
        # width: 1~6
        # examples:
        # 0: n/a
        # 1: 1
        # 10: 10
        # 100: 100
        # 1000: 1.0K
        # 10000: 10.0K
        # 100000: 100.0K
        # 1000000: 1.0M
        # -10: -11
        if num == 0:
            return 'n/a'
        else:
            return Formatter.format_int(num)

    markup_int_or_na = _markup(format_int_or_na, attr_int)
    make_int_or_na_text = _make_text(markup_int_or_na, **_numeric)

    # time

    @staticmethod
    def format_time(sec):
        # width: 1~6 (most cases)
        # examples:
        # 0: 0
        # 0.000001: 1us
        # 0.000123: 123us
        # 0.012345: 12ms
        # 0.123456: 123ms
        # 1.234567: 1.2sec
        # 12.34567: 12.3sec
        # 123.4567: 2min3s
        # 6120: 102min
        if sec == 0:
            return '0'
        elif sec < 1e-3:
            # 1us ~ 999us
            return '{:.0f}us'.format(sec * 1e6)
        elif sec < 1:
            # 1ms ~ 999ms
            return '{:.0f}ms'.format(sec * 1e3)
        elif sec < 60:
            # 1.0sec ~ 59.9sec
            return '{:.1f}sec'.format(sec)
        elif sec < 600:
            # 1min0s ~ 9min59s
            return '{:.0f}min{:.0f}s'.format(sec // 60, sec % 60)
        else:
            return '{:.0f}min'.format(sec // 60)

    @staticmethod
    def attr_time(sec):
        if sec == 0:
            return 'zero'
        elif sec < 1e-3:
            return 'usec'
        elif sec < 1:
            return 'msec'
        elif sec < 60:
            return 'sec'
        else:
            return 'min'

    markup_time = _markup(format_time, attr_time)
    make_time_text = _make_text(markup_time, **_numeric)

    # stats

    @staticmethod
    def markup_stats(stats):
        if stats.name:
            loc = ('({0}:{1})'
                   ''.format(stats.module or stats.filename, stats.lineno))
            return [('name', stats.name), ' ', ('loc', loc)]
        else:
            return ('loc', stats.module or stats.filename)

    make_stat_text = _make_text(markup_stats, wrap='clip')

    del _markup
    del _make_text


fmt = Formatter


class StatisticsWidget(urwid.TreeWidget):

    signals = ['expanded', 'collapsed']
    icon_chars = ('+', '-', ' ')  # collapsed, expanded, leaf

    def __init__(self, node):
        super(StatisticsWidget, self).__init__(node)
        self._w = urwid.AttrWrap(self._w, None, StatisticsViewer.focus_map)

    def selectable(self):
        return True

    @property
    def expanded(self):
        return self._expanded

    @expanded.setter
    def expanded(self, expanded):
        in_init = not hasattr(self, 'expanded')
        self._expanded = expanded
        if in_init:
            return
        if expanded:
            urwid.emit_signal(self, 'expanded')
        else:
            urwid.emit_signal(self, 'collapsed')

    def get_mark(self):
        """Gets an expanded, collapsed, or leaf icon."""
        if self.is_leaf:
            char = self.icon_chars[2]
        else:
            char = self.icon_chars[int(self.expanded)]
        return urwid.SelectableIcon(('mark', char), 0)

    def load_inner_widget(self):
        node = self.get_node()
        return node.table.make_row(node)

    def get_indented_widget(self):
        icon = self.get_mark()
        widget = self.get_inner_widget()
        node = self.get_node()
        widget = urwid.Columns([('fixed', 1, icon), widget], 1)
        indent = (node.get_depth() - 1)
        widget = urwid.Padding(widget, left=indent)
        return widget

    def update_mark(self):
        widget = self._w.base_widget
        try:
            widget.widget_list[0] = self.get_mark()
        except (TypeError, AttributeError):
            return

    def update_expanded_icon(self):
        self.update_mark()

    def expand(self):
        self.expanded = True
        self.update_mark()

    def collapse(self):
        self.expanded = False
        self.update_mark()

    def keypress(self, size, key):
        command = self._command_map[key]
        if command == urwid.ACTIVATE:
            key = '-' if self.expanded else '+'
        elif command == urwid.CURSOR_RIGHT:
            key = '+'
        elif self.expanded and command == urwid.CURSOR_LEFT:
            key = '-'
        return super(StatisticsWidget, self).keypress(size, key)


class EmptyWidget(urwid.Widget):
    """A widget which doesn't render anything."""

    def __init__(self, rows=0):
        super(EmptyWidget, self).__init__()
        self._rows = rows

    def rows(self, size, focus=False):
        return self._rows

    def render(self, size, focus=False):
        return urwid.SolidCanvas(' ', size[0], self.rows(size, focus))


class RootStatisticsWidget(StatisticsWidget):

    def load_inner_widget(self):
        return EmptyWidget()

    def get_indented_widget(self):
        return self.get_inner_widget()

    def get_mark(self):
        raise TypeError('Statistics widget has no mark')

    def update(self):
        pass

    def unexpand(self):
        pass


class StatisticsNodeBase(urwid.TreeNode):

    def __init__(self, stats=None, parent=None, key=None, depth=None,
                 table=None):
        super(StatisticsNodeBase, self).__init__(stats, parent, key, depth)
        self.table = table

    def get_focus(self):
        widget, focus = super(StatisticsNodeBase, self).get_focus()
        if self.table is not None:
            self.table.walker.set_focus(self)
        return widget, focus

    def get_widget(self, reload=False):
        if self._widget is None or reload:
            self._widget = self.load_widget()
            self.setup_widget(self._widget)
        return self._widget

    def load_widget(self):
        return self._widget_class(self)

    def setup_widget(self, widget):
        if self.table is None:
            return
        stats = self.get_value()
        if hash(stats) in self.table._expanded_stat_hashes:
            widget.expand()


class NullStatisticsWidget(StatisticsWidget):

    def __init__(self, node):
        urwid.TreeWidget.__init__(self, node)

    def get_inner_widget(self):
        widget = urwid.Text(('weak', '- Not Available -'), align='center')
        widget = urwid.Filler(widget)
        widget = urwid.BoxAdapter(widget, 3)
        return widget


class NullStatisticsNode(StatisticsNodeBase):

    _widget_class = NullStatisticsWidget


class LeafStatisticsNode(StatisticsNodeBase):

    _widget_class = StatisticsWidget


class StatisticsNode(StatisticsNodeBase, urwid.ParentNode):

    def deep_usage(self):
        stats = self.get_value()
        table = self.get_root()
        try:
            return stats.deep_time / table.cpu_time
        except AttributeError:
            return 0.0

    def load_widget(self):
        if self.is_root():
            widget_class = RootStatisticsWidget
        else:
            widget_class = StatisticsWidget
        widget = widget_class(self)
        widget.collapse()
        return widget

    def setup_widget(self, widget):
        super(StatisticsNode, self).setup_widget(widget)
        if self.get_depth() == 0:
            # Just expand the root node.
            widget.expand()
            return
        table = self.table
        if table is None:
            return
        on(widget, 'expanded', table._widget_expanded, widget)
        on(widget, 'collapsed', table._widget_collapsed, widget)

    def load_child_keys(self):
        stats = self.get_value()
        if stats is None:
            return ()
        return stats.sorted(self.table.order)

    def load_child_node(self, stats):
        depth = self.get_depth() + 1
        node_class = StatisticsNode if len(stats) else LeafStatisticsNode
        return node_class(stats, self, stats, depth, self.table)


class StatisticsListBox(urwid.TreeListBox):

    signals = ['focus_changed']

    def change_focus(self, *args, **kwargs):
        super(StatisticsListBox, self).change_focus(*args, **kwargs)
        focus = self.get_focus()
        urwid.emit_signal(self, 'focus_changed', focus)


class StatisticsWalker(urwid.TreeWalker):

    signals = ['focus_changed']

    def set_focus(self, focus):
        super(StatisticsWalker, self).set_focus(focus)
        urwid.emit_signal(self, 'focus_changed', focus)


class StatisticsTable(urwid.WidgetWrap):

    #: The column declarations.  Define it with a list of (name, align, width,
    #: order) tuples.
    columns = [('FUNCTION', 'left', ('weight', 1), sortkeys.by_function)]

    #: The initial order.
    order = sortkeys.by_function

    #: The children statistics layout.  One of `NESTED` or `FLAT`.
    layout = NESTED

    title = None
    stats = None
    time = None

    def __init__(self, viewer):
        self._expanded_stat_hashes = set()
        self.walker = StatisticsWalker(NullStatisticsNode())
        on(self.walker, 'focus_changed', self._walker_focus_changed)
        tbody = StatisticsListBox(self.walker)
        thead = urwid.AttrMap(self.make_columns([
            urwid.Text(name, align, 'clip')
            for name, align, __, __ in self.columns
        ]), None)
        header = urwid.Columns([])
        widget = urwid.Frame(tbody, urwid.Pile([header, thead]))
        super(StatisticsTable, self).__init__(widget)
        self.viewer = viewer
        self.update_frame()

    def make_row(self, node):
        stats = node.get_value()
        return self.make_columns(self.make_cells(node, stats))

    def make_cells(self, node, stats):
        yield fmt.make_stat_text(stats)

    @classmethod
    def make_columns(cls, column_widgets):
        widget_list = []
        widths = (width for __, __, width, __ in cls.columns)
        for width, widget in zip(widths, column_widgets):
            widget_list.append(width + (widget,))
        return urwid.Columns(widget_list, 1)

    @property
    def tbody(self):
        return self._w.body

    @tbody.setter
    def tbody(self, body):
        self._w.body = body

    @property
    def thead(self):
        return self._w.header.contents[1][0]

    @thead.setter
    def thead(self, thead):
        self._w.header.contents[1] = (thead, ('pack', None))

    @property
    def header(self):
        return self._w.header.contents[0][0]

    @header.setter
    def header(self, header):
        self._w.header.contents[0] = (header, ('pack', None))

    @property
    def footer(self):
        return self._w.footer

    @footer.setter
    def footer(self, footer):
        self._w.footer = footer

    def get_focus(self):
        return self.tbody.get_focus()

    def set_focus(self, focus):
        self.tbody.set_focus(focus)

    def get_path(self):
        """Gets the path to the focused statistics. Each step is a hash of
        statistics object.
        """
        path = deque()
        __, node = self.get_focus()
        while not node.is_root():
            stats = node.get_value()
            path.appendleft(hash(stats))
            node = node.get_parent()
        return path

    def find_node(self, node, path):
        """Finds a node by the given path from the given node."""
        for hash_value in path:
            if isinstance(node, LeafStatisticsNode):
                break
            for stats in node.get_child_keys():
                if hash(stats) == hash_value:
                    node = node.get_child_node(stats)
                    break
            else:
                break
        return node

    def get_stats(self):
        return self.stats

    def set_result(self, stats, cpu_time=0.0, wall_time=0.0,
                   title=None, at=None):
        self.stats = stats
        self.cpu_time = cpu_time
        self.wall_time = wall_time
        self.title = title
        self.at = at
        self.refresh()

    def set_layout(self, layout):
        if layout == self.layout:
            return  # Ignore.
        self.layout = layout
        self.refresh()

    def sort_stats(self, order=sortkeys.by_deep_time):
        assert callable(order)
        if order == self.order:
            return  # Ignore.
        self.order = order
        self.refresh()

    def shift_order(self, delta):
        orders = [order for __, __, __, order in self.columns if order]
        x = orders.index(self.order)
        order = orders[(x + delta) % len(orders)]
        self.sort_stats(order)

    def refresh(self):
        stats = self.get_stats()
        if stats is None:
            return
        if self.layout == FLAT:
            stats = FlatFrozenStatistics.flatten(stats)
        node = StatisticsNode(stats, table=self)
        path = self.get_path()
        node = self.find_node(node, path)
        self.set_focus(node)

    def update_frame(self, focus=None):
        # Set thead attr.
        if self.viewer.paused:
            thead_attr = 'thead.paused'
        elif not self.viewer.active:
            thead_attr = 'thead.inactive'
        else:
            thead_attr = 'thead'
        self.thead.set_attr_map({None: thead_attr})
        # Set sorting column in thead attr.
        for x, (__, __, __, order) in enumerate(self.columns):
            attr = thead_attr + '.sorted' if order is self.order else None
            widget = self.thead.base_widget.contents[x][0]
            text, __ = widget.get_text()
            widget.set_text((attr, text))
        if self.viewer.paused:
            return
        # Update header.
        stats = self.get_stats()
        if stats is None:
            return
        title = self.title
        time = self.time
        if title or time:
            if time is not None:
                time_string = '{:%H:%M:%S}'.format(time)
            if title and time:
                markup = [('weak', title), ' ', time_string]
            elif title:
                markup = title
            else:
                markup = time_string
            meta_info = urwid.Text(markup, align='right')
        else:
            meta_info = None
        fraction_string = '({0}/{1})'.format(
            fmt.format_time(self.cpu_time),
            fmt.format_time(self.wall_time))
        try:
            cpu_usage = self.cpu_time / self.wall_time
        except ZeroDivisionError:
            cpu_usage = 0.0
        cpu_info = urwid.Text([
            'CPU ', fmt.markup_percent(cpu_usage, unit=True),
            ' ', ('weak', fraction_string)])
        # Set header columns.
        col_opts = ('weight', 1, False)
        self.header.contents = \
            [(w, col_opts) for w in [cpu_info, meta_info] if w]

    def focus_hotspot(self, size):
        widget, __ = self.tbody.get_focus()
        while widget:
            node = widget.get_node()
            widget.expand()
            widget = widget.first_child()
        self.tbody.change_focus(size, node)

    def defocus(self):
        __, node = self.get_focus()
        self.set_focus(node.get_root())

    def keypress(self, size, key):
        command = self._command_map[key]
        if key == ']':
            self.shift_order(+1)
            return True
        elif key == '[':
            self.shift_order(-1)
            return True
        elif key == '>':
            self.focus_hotspot(size)
            return True
        elif key == '\\':
            layout = {FLAT: NESTED, NESTED: FLAT}[self.layout]
            self.set_layout(layout)
            return True
        command = self._command_map[key]
        if command == 'menu':
            # key: ESC.
            self.defocus()
            return True
        elif command == urwid.CURSOR_RIGHT:
            if self.layout == FLAT:
                return True  # Ignore.
            widget, node = self.tbody.get_focus()
            if widget.expanded:
                heavy_widget = widget.first_child()
                if heavy_widget is not None:
                    heavy_node = heavy_widget.get_node()
                    self.tbody.change_focus(size, heavy_node)
                return True
        elif command == urwid.CURSOR_LEFT:
            if self.layout == FLAT:
                return True  # Ignore.
            widget, node = self.tbody.get_focus()
            if not widget.expanded:
                parent_node = node.get_parent()
                if parent_node is not None and not parent_node.is_root():
                    self.tbody.change_focus(size, parent_node)
                return True
        elif command == urwid.ACTIVATE:
            # key: Enter or Space.
            if self.viewer.paused:
                self.viewer.resume()
            else:
                self.viewer.pause()
            return True
        return super(StatisticsTable, self).keypress(size, key)

    # Signal handlers.

    def _walker_focus_changed(self, focus):
        self.update_frame(focus)

    def _widget_expanded(self, widget):
        stats = widget.get_node().get_value()
        self._expanded_stat_hashes.add(hash(stats))

    def _widget_collapsed(self, widget):
        stats = widget.get_node().get_value()
        self._expanded_stat_hashes.discard(hash(stats))


class StatisticsViewer(object):

    weak_color = 'light green'
    palette = [
        ('weak', weak_color, ''),
        ('focus', 'standout', '', 'standout'),
        # ui
        ('thead', 'dark cyan, standout', '', 'standout'),
        ('thead.paused', 'dark red, standout', '', 'standout'),
        ('thead.inactive', 'brown, standout', '', 'standout'),
        ('mark', 'dark magenta', ''),
        # risk
        ('danger', 'dark red', '', 'blink'),
        ('caution', 'light red', '', 'blink'),
        ('warning', 'brown', '', 'blink'),
        ('notice', 'dark green', '', 'blink'),
        # clock
        ('min', 'dark red', ''),
        ('sec', 'brown', ''),
        ('msec', '', ''),
        ('usec', weak_color, ''),
        # etc
        ('zero', weak_color, ''),
        ('name', 'bold', ''),
        ('loc', 'dark blue', ''),
    ]
    # add thead.*.sorted palette entries
    for entry in palette[:]:
        attr = entry[0]
        if attr is not None and attr.startswith('thead'):
            fg, bg, mono = entry[1:4]
            palette.append((attr + '.sorted', fg + ', underline',
                            bg, mono + ', underline'))

    focus_map = {None: 'focus'}
    focus_map.update((x[0], 'focus') for x in palette)

    #: Whether the viewer is active.
    active = False

    #: Whether the viewer is paused.
    paused = False

    def unhandled_input(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def __init__(self):
        self.table = StatisticsTable(self)
        self.widget = urwid.Padding(self.table, right=1)

    def loop(self, *args, **kwargs):
        kwargs.setdefault('unhandled_input', self.unhandled_input)
        loop = urwid.MainLoop(self.widget, self.palette, *args, **kwargs)
        return loop

    def set_profiler_class(self, profiler_class):
        table_class = profiler_class.table_class
        # NOTE: Don't use isinstance() at the below line.
        if type(self.table) is table_class:
            return
        self.table = table_class(self)
        self.widget.original_widget = self.table

    def set_result(self, stats, cpu_time=0.0, wall_time=0.0,
                   title=None, at=None):
        self._final_result = (stats, cpu_time, wall_time, title, at)
        if not self.paused:
            self.update_result()

    def update_result(self):
        """Updates the result on the table."""
        try:
            if self.paused:
                result = self._paused_result
            else:
                result = self._final_result
        except AttributeError:
            self.table.update_frame()
            return
        stats, cpu_time, wall_time, title, at = result
        self.table.set_result(stats, cpu_time, wall_time, title, at)

    def activate(self):
        self.active = True
        self.table.update_frame()

    def inactivate(self):
        self.active = False
        self.table.update_frame()

    def pause(self):
        self.paused = True
        try:
            self._paused_result = self._final_result
        except AttributeError:
            pass
        self.table.update_frame()

    def resume(self):
        self.paused = False
        try:
            del self._paused_result
        except AttributeError:
            pass
        self.update_result()


def bind_vim_keys(urwid=urwid):
    urwid.command_map['h'] = urwid.command_map['left']
    urwid.command_map['j'] = urwid.command_map['down']
    urwid.command_map['k'] = urwid.command_map['up']
    urwid.command_map['l'] = urwid.command_map['right']


def bind_game_keys(urwid=urwid):
    urwid.command_map['a'] = urwid.command_map['left']
    urwid.command_map['s'] = urwid.command_map['down']
    urwid.command_map['w'] = urwid.command_map['up']
    urwid.command_map['d'] = urwid.command_map['right']
