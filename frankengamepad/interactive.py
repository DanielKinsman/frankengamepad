import concurrent.futures
import evdev.ecodes
import IPython
import functools
import time
import frankengamepad.device


IPYTHON_HEADER = """Try something like:

    button(devices['frankengamepad0'], evdev.ecodes.BTN_A, value=1, delay=2)
    button(devices['frankengamepad0'], evdev.ecodes.BTN_A, value=0, delay=4)

Type `exit` to continue and start running the frankengamepad tranlsations."""


def _delay_call(executor, func, delay, *args, **kwargs):
    def do_it():
        time.sleep(delay)
        func(*args, **kwargs)

    if not delay:
        func(*args, **kwargs)
    else:
        executor.submit(do_it)


def _button_toggle(executor, uinput, code, delay=0):
    _delay_call(executor, frankengamepad.device.button_toggle, delay, uinput, code)


def _button(executor, uinput, code, value=1, delay=0):
    _delay_call(executor, frankengamepad.device.button, delay, uinput, code, value=value)


def session(devices):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        button = functools.partial(_button, executor)
        button_toggle = functools.partial(_button_toggle, executor)
        IPython.embed(header=IPYTHON_HEADER)
