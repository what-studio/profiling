# -*- coding: utf-8 -*-
from collections import deque

from profiling.utils import frame_stack
from utils import foo, mock_code_names


def test_frame_stack():
    def to_code_names(frames):
        code_names = deque()
        for frame in reversed(frames):
            code_name = frame.f_code.co_name
            if code_name not in mock_code_names:
                break
            code_names.appendleft(code_name)
        return list(code_names)
    frame = foo()
    frames = frame_stack(frame)
    assert to_code_names(frames) == ['foo', 'bar', 'baz']
    # top frame
    frames = frame_stack(frame, top_frame=frame.f_back)
    assert to_code_names(frames) == ['bar', 'baz']
    # top code
    frames = frame_stack(frame, top_code=frame.f_back.f_code)
    assert to_code_names(frames) == ['bar', 'baz']
    # both of top frame and top code
    frames = frame_stack(frame, top_frame=frame.f_back,
                         top_code=frame.f_back.f_code)
    assert to_code_names(frames) == ['bar', 'baz']
