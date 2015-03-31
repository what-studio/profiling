#include "Python.h"
#include "frameobject.h"


static PyObject *
frame_stack(PyObject *self, PyObject *args)
{
    PyFrameObject* frame;
    const PyFrameObject* top_frame;
    const PyCodeObject* top_code;
    if (!PyArg_ParseTuple(args, "OOO", &frame, &top_frame, &top_code))
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
        if (PyList_Append(frame_stack, (PyObject*)frame))
        {
            return NULL;
        }
        if (frame == top_frame || frame->f_code == top_code)
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
