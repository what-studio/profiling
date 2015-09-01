#include "Python.h"
#include "frameobject.h"

static PyObject *
frame_stack(PyObject *self, PyObject *args)
{
    // frame_stack(frame, top_frames, top_codes, upper_frames, upper_codes)
    // returns a list of frames.
    PyFrameObject* frame;
    const PySetObject* top_frames;
    const PySetObject* top_codes;
    const PySetObject* upper_frames;
    const PySetObject* upper_codes;
    if (!PyArg_ParseTuple(args, "OOOOO", &frame, &top_frames, &top_codes,
                          &upper_frames, &upper_codes))
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
        if (PySet_Contains(upper_frames, frame) == 1 ||
            PySet_Contains(upper_codes, frame->f_code) == 1)
        {
            break;
        }
        if (PyList_Append(frame_stack, (PyObject*)frame))
        {
            return NULL;
        }
        if (PySet_Contains(top_frames, frame) == 1 ||
            PySet_Contains(top_codes, frame->f_code) == 1)
        {
            break;
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
