#include "Python.h"
#include "frameobject.h"

#define PYOBJ PyObject*

static PyObject *
frame_stack(PyObject *self, PyObject *args)
{
    // frame_stack(frame, base_frame, base_code, ignored_frames, ignored_codes)
    // returns a list of frames.
    PyFrameObject* frame;
    const PyFrameObject* base_frame;
    const PyCodeObject* base_code;
    const PySetObject* ignored_frames;
    const PySetObject* ignored_codes;
    if (!PyArg_ParseTuple(args, "OOOOO", &frame, &base_frame, &base_code,
                                         &ignored_frames, &ignored_codes))
    {
        return NULL;
    }
    PyObject* frame_stack = PyList_New(0);
    if (frame_stack == NULL)
    {
        return NULL;
    }
    while (frame != NULL)
    {
        if (frame == base_frame || frame->f_code == base_code)
        {
            break;
        }
        if (PySet_Contains((PYOBJ)ignored_frames, (PYOBJ)frame) == 0 &&
            PySet_Contains((PYOBJ)ignored_codes, (PYOBJ)frame->f_code) == 0)
        {
            // Not ignored.
            if (PyList_Append(frame_stack, (PyObject*)frame) == -1)
            {
                return NULL;
            }
        }
        frame = frame->f_back;
    }
    PyList_Reverse(frame_stack);
    return frame_stack;
}

static PyMethodDef SpeedupMethods[] = {
    {"frame_stack", frame_stack, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}
};

// https://docs.python.org/3/howto/cporting.html
#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef SpeedupModule = {
    PyModuleDef_HEAD_INIT,
    "speedup",
    NULL,
    -1,
    SpeedupMethods
};
PyMODINIT_FUNC
PyInit_speedup(void)
{
    return PyModule_Create(&SpeedupModule);
}
#else
PyMODINIT_FUNC
initspeedup(void)
{
    (void) Py_InitModule("speedup", SpeedupMethods);
}
#endif
