# -*- coding: utf-8 -*-
"""
    profiling.viewer
    ~~~~~~~~~~~~~~~~

    A text user interface application which inspects statistics.  To run it
    easily do:

    .. sourcecode:: console

       $ python -m profiling view SOURCE

    ::

       viewer = StatisticsViewer()
       loop = viewer.loop()
       loop.run()

"""
from __future__ import absolute_import
from collections import deque

import urwid
from urwid import connect_signal as on

from . import sortkeys


__all__ = ['StatisticsTable', 'StatisticsViewer']


class Formatter(object):

    def _markup(get_string, get_attr=None):
        def markup(self, *args, **kwargs):
            string = get_string(self, *args, **kwargs)
            if get_attr is None:
                return string
            attr = get_attr(self, *args, **kwargs)
            return (attr, string)
        return markup

    _numeric = {'align': 'right', 'wrap': 'clip'}

    def _make_text(get_markup, **text_kwargs):
        def make_text(self, *args, **kwargs):
            markup = get_markup(self, *args, **kwargs)
            return urwid.Text(markup, **text_kwargs)
        return make_text

    # percent

    def format_percent(self, ratio, denom=1, unit=True):
        try:
            ratio /= float(denom)
        except ZeroDivisionError:
            ratio = 0
        ratio = round(ratio, 4)
        if ratio >= 1:
            precision = 0
        elif ratio >= 0.1:
            precision = 1
        else:
            precision = 2
        string = ('{:.' + str(precision) + 'f}').format(ratio * 100)
        if unit:
            return string + '%'
        else:
            return string

    def attr_ratio(self, ratio, denom=1, unit=True):
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

    def format_int(self, num):
        return '{:.0f}'.format(num)

    def attr_int(self, num):
        return None if num else 'zero'

    markup_int = _markup(format_int, attr_int)
    make_int_text = _make_text(markup_int, **_numeric)

    # int or n/a

    def format_int_or_na(self, num):
        if not num:
            return 'n/a'
        return self.format_int(num)

    markup_int_or_na = _markup(format_int_or_na, attr_int)
    make_int_or_na_text = _make_text(markup_int_or_na, **_numeric)

    # time

    def format_time(self, sec):
        if sec == 0:
            return '0'
        elif sec < 1:
            return '{:,.0f}'.format(sec * 1e6).replace(',', '.')
        else:
            return '{:.2f}s'.format(sec)

    def attr_time(self, sec):
        if sec == 0:
            return 'zero'
        elif sec < 1:
            return 'usec'
        else:
            return 'sec'

    markup_time = _markup(format_time, attr_time)
    make_time_text = _make_text(markup_time, **_numeric)

    # stat

    def markup_stat(self, stat):
        if stat.name:
            loc = '({0}:{1})'.format(stat.module or stat.filename, stat.lineno)
            return [('name', stat.name), ' ', ('loc', loc)]
        else:
            return ('loc', stat.module or stat.filename)

    make_stat_text = _make_text(markup_stat, wrap='clip')

    del _markup
    del _make_text


fmt = Formatter()


class StatisticWidget(urwid.TreeWidget):

    signals = ['expanded', 'collapsed']
    icon_chars = ('+', '-', ' ')  # collapsed, expanded, leaf

    def __init__(self, node):
        super(StatisticWidget, self).__init__(node)
        self._w = urwid.AttrWrap(self._w, None, StatisticsViewer.focus_map)

    def get_indented_widget(self):
        # don't indent at here.
        return self.get_inner_widget()

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

    def get_function_widget(self):
        """Gets the cached function identification widget."""
        widget = self._w.base_widget
        return widget.widget_list[1]

    def load_function_widget(self, node=None, stat=None):
        """Creates an indented function identification widget."""
        if node is None:
            node = self.get_node()
        if stat is None:
            stat = node.get_value()
        icon = self.get_mark()
        indent = (node.get_depth() - 1)
        widget = fmt.make_stat_text(stat)
        widget = urwid.Columns([('fixed', 1, icon), widget], 1)
        widget = urwid.Padding(widget, left=indent)
        return widget

    def load_inner_widget(self):
        node = self.get_node()
        stat = node.get_value()
        stats = node.get_root().get_value()
        if node.table.order is sortkeys.by_total_calls:
            numer = stat.total_calls
            denom = stats.total_calls
        elif node.table.order is sortkeys.by_total_time:
            numer = stat.total_time
            denom = stats.cpu_time
        elif node.table.order is sortkeys.by_total_time_per_call:
            numer = stat.total_time_per_call
            denom = stats.cpu_time / stats.total_calls
        elif node.table.order is sortkeys.by_own_calls:
            numer = stat.own_calls
            denom = stats.total_calls
        elif node.table.order is sortkeys.by_own_time:
            numer = stat.own_time
            denom = stats.cpu_time
        elif node.table.order is sortkeys.by_own_time_per_call:
            numer = stat.own_time_per_call
            denom = stats.cpu_time / stats.total_calls
        else:
            numer, denom = 0, 1
        function_widget = self.load_function_widget(node, stat)
        return StatisticsTable.make_columns([
            fmt.make_percent_text(numer, denom, unit=False),
            function_widget,
            fmt.make_int_or_na_text(stat.total_calls),
            fmt.make_time_text(stat.total_time),
            fmt.make_time_text(stat.total_time_per_call),
            fmt.make_int_or_na_text(stat.own_calls),
            fmt.make_time_text(stat.own_time),
            fmt.make_time_text(stat.own_time_per_call),
        ])

    def update_mark(self):
        try:
            icon = self.get_mark()
        except TypeError:
            return
        function_widget = self.get_function_widget()
        function_widget.base_widget.widget_list[0] = icon

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
        return super(StatisticWidget, self).keypress(size, key)


class EmptyWidget(urwid.Widget):
    """A widget which doesn't render anything."""

    def __init__(self, rows=0):
        super(EmptyWidget, self).__init__()
        self._rows = rows

    def rows(self, size, focus=False):
        return self._rows

    def render(self, size, focus=False):
        return urwid.SolidCanvas(' ', size[0], self.rows(size, focus))


class StatisticsWidget(StatisticWidget):

    def load_inner_widget(self):
        return EmptyWidget()

    def get_mark(self):
        raise TypeError('Statistics widget has no mark')

    def update(self):
        pass

    def unexpand(self):
        pass


class StatisticNodeBase(urwid.TreeNode):

    def __init__(self, stat=None, parent=None, key=None, depth=None,
                 table=None):
        super(StatisticNodeBase, self).__init__(stat, parent, key, depth)
        self.table = table

    def get_focus(self):
        widget, focus = super(StatisticNodeBase, self).get_focus()
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
        stat = self.get_value()
        if hash(stat) in self.table._expanded_stat_hashes:
            widget.expand()


class NullStatisticWidget(StatisticWidget):

    def __init__(self, node):
        urwid.TreeWidget.__init__(self, node)

    def get_inner_widget(self):
        widget = urwid.Text(('weak', '- Not Available -'), align='center')
        widget = urwid.Filler(widget)
        widget = urwid.BoxAdapter(widget, 3)
        return widget


class NullStatisticNode(StatisticNodeBase):

    _widget_class = NullStatisticWidget


class LeafStatisticNode(StatisticNodeBase):

    _widget_class = StatisticWidget


class StatisticNode(StatisticNodeBase, urwid.ParentNode):

    def total_usage(self):
        stat = self.get_value()
        stats = self.get_root().get_value()
        try:
            return stat.total_time / stats.cpu_time
        except AttributeError:
            return 0.0

    def load_widget(self):
        if self.is_root():
            widget_class = StatisticsWidget
        else:
            widget_class = StatisticWidget
        widget = widget_class(self)
        widget.collapse()
        return widget

    def setup_widget(self, widget):
        super(StatisticNode, self).setup_widget(widget)
        if self.get_depth() == 0:
            # just expand the root node
            widget.expand()
            return
        table = self.table
        if table is None:
            return
        on(widget, 'expanded', table._widget_expanded, widget)
        on(widget, 'collapsed', table._widget_collapsed, widget)

    def load_child_keys(self):
        stat = self.get_value()
        if stat is None:
            return ()
        return stat.sorted(self.table.order)

    def load_child_node(self, stat):
        depth = self.get_depth() + 1
        node_class = StatisticNode if len(stat) else LeafStatisticNode
        return node_class(stat, self, stat, depth, self.table)


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

    #: The column declarations.
    columns = [
        # name, align, width, order
        ('%', 'right', (4,), None),
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('TOTAL#', 'right', (6,), sortkeys.by_total_calls),
        ('TIME', 'right', (6,), sortkeys.by_total_time),
        ('/CALL', 'right', (6,), sortkeys.by_total_time_per_call),
        ('OWN#', 'right', (6,), sortkeys.by_own_calls),
        ('TIME', 'right', (6,), sortkeys.by_own_time),
        ('/CALL', 'right', (6,), sortkeys.by_own_time_per_call),
    ]

    #: The initial order.
    order = sortkeys.by_total_time

    #: Whether the viewer is active.
    active = False

    #: Whether the viewer is paused.
    paused = False

    title = None
    stats = None
    time = None

    def __init__(self):
        cls = type(self)
        self._expanded_stat_hashes = set()
        self.walker = StatisticsWalker(NullStatisticNode())
        on(self.walker, 'focus_changed', self._walker_focus_changed)
        tbody = StatisticsListBox(self.walker)
        thead = urwid.AttrMap(cls.make_columns([
            urwid.Text(name, align, 'clip')
            for name, align, __, __ in self.columns
        ]), None)
        header = urwid.Columns([])
        widget = urwid.Frame(tbody, urwid.Pile([header, thead]))
        super(StatisticsTable, self).__init__(widget)
        self.update_frame()

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
        """Gets the path to the focused statistic. Each step is a hash of
        statistic object.
        """
        path = deque()
        __, node = self.get_focus()
        while not node.is_root():
            stat = node.get_value()
            path.appendleft(hash(stat))
            node = node.get_parent()
        return path

    def find_node(self, node, path):
        """Finds a node by the given path from the given node."""
        for hash_value in path:
            if isinstance(node, LeafStatisticNode):
                break
            for stat in node.get_child_keys():
                if hash(stat) == hash_value:
                    node = node.get_child_node(stat)
                    break
            else:
                break
        return node

    def get_stats(self):
        return self.stats

    def set_stats(self, stats, title=None, time=None):
        self.stats = stats
        self.title = title
        self.time = time
        if not self.paused:
            self.activate()
            self.refresh()

    def sort_stats(self, order=sortkeys.by_total_time):
        assert callable(order)
        self.order = order
        self.refresh()

    def shift_order(self, delta):
        orders = [order for __, __, __, order in self.columns if order]
        x = orders.index(self.order)
        order = orders[(x + delta) % len(orders)]
        self.sort_stats(order)

    def pause(self):
        self.paused = True
        self.update_frame()

    def resume(self):
        self.paused = False
        try:
            stats, title, time = self._pending
        except AttributeError:
            self.activate()
        else:
            del self._pending
            self.set_stats(stats, title, time)

    def activate(self):
        self.active = True
        self.update_frame()

    def inactivate(self):
        self.active = False
        self.update_frame()

    def refresh(self):
        stats = self.get_stats()
        node = StatisticNode(stats, table=self)
        path = self.get_path()
        node = self.find_node(node, path)
        self.set_focus(node)

    def update_frame(self, focus=None):
        # set thead attr
        if self.paused:
            thead_attr = 'thead.paused'
        elif not self.active:
            thead_attr = 'thead.inactive'
        else:
            thead_attr = 'thead'
        self.thead.set_attr_map({None: thead_attr})
        # set sorting column in thead attr
        for x, (__, __, __, order) in enumerate(self.columns):
            attr = thead_attr + '.sorted' if order is self.order else None
            widget = self.thead.base_widget.contents[x][0]
            text, __ = widget.get_text()
            widget.set_text((attr, text))
        if self.paused:
            return
        # update header
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
            fmt.format_time(stats.cpu_time),
            fmt.format_time(stats.wall_time))
        cpu_info = urwid.Text([
            'CPU ', fmt.markup_percent(stats.cpu_usage),
            ' ', ('weak', fraction_string)])
        # set header columns
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
        base = super(StatisticsTable, self)
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
        elif command == self._command_map['esc']:
            self.defocus()
            return True
        elif command == self._command_map['right']:
            widget, node = self.tbody.get_focus()
            if widget.expanded:
                heavy_widget = widget.first_child()
                if heavy_widget is not None:
                    heavy_node = heavy_widget.get_node()
                    self.tbody.change_focus(size, heavy_node)
                return True
        elif command == self._command_map['left']:
            widget, node = self.tbody.get_focus()
            if not widget.expanded:
                parent_node = node.get_parent()
                if not parent_node.is_root():
                    self.tbody.change_focus(size, parent_node)
                return True
        elif command == self._command_map[' ']:
            if self.paused:
                self.resume()
            else:
                self.pause()
            return True
        return base.keypress(size, key)

    # signal handlers

    def _walker_focus_changed(self, focus):
        self.update_frame(focus)

    def _widget_expanded(self, widget):
        stat = widget.get_node().get_value()
        self._expanded_stat_hashes.add(hash(stat))

    def _widget_collapsed(self, widget):
        stat = widget.get_node().get_value()
        self._expanded_stat_hashes.discard(hash(stat))


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
        ('sec', 'brown', ''),
        ('msec', 'dark green', ''),
        ('usec', '', ''),
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

    def unhandled_input(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def __init__(self):
        self.table = StatisticsTable()
        self.widget = urwid.Padding(self.table, right=1)

    def loop(self, *args, **kwargs):
        kwargs.setdefault('unhandled_input', self.unhandled_input)
        loop = urwid.MainLoop(self.widget, self.palette, *args, **kwargs)
        return loop

    def set_stats(self, stats, title=None, time=None):
        self.table.set_stats(stats, title, time)

    def activate(self):
        return self.table.activate()

    def inactivate(self):
        return self.table.inactivate()

    def use_vim_command_map(self):
        urwid.command_map['h'] = urwid.command_map['left']
        urwid.command_map['j'] = urwid.command_map['down']
        urwid.command_map['k'] = urwid.command_map['up']
        urwid.command_map['l'] = urwid.command_map['right']

    def use_game_command_map(self):
        urwid.command_map['a'] = urwid.command_map['left']
        urwid.command_map['s'] = urwid.command_map['down']
        urwid.command_map['w'] = urwid.command_map['up']
        urwid.command_map['d'] = urwid.command_map['right']
