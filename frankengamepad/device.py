import asyncio
import evdev
import logging
import signal
import time
import frankengamepad.config


logger = logging.getLogger(__name__)


class NoDeviceError(Exception):
    pass


def get_device(config):
    """
    Get the device from the source configuration.
    :param config: The "source" device configuration containing a "name"
                   (e.g. "Xbox 360 Wireless Receiver (XBOX)") and/or a
                   "path" (e.g. "/dev/input/event19")
    :type config: collections.Mapping
    :return: the input device
    :rtype: evdev.InputDevice
    """
    try:
        device = evdev.InputDevice(config["path"])
        try:
            if device.name == config["name"]:
                return device
        except KeyError:
            return device  # No name specified in config
    except(KeyError, FileNotFoundError):
        pass

    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        if device.name == config["name"]:
            return device

    raise NoDeviceError(f"No device found with name `{config.get('name')}` path `{config.get('path')}`")


async def watch_device(config, franken_uinputs):
    """
    Watch the device specified in the source configuration and translate events
    from the source device to a franken gamepad.
    :param config: The device configuration (from the yaml "sources" configuration section)
    :type config: collections.Mapping
    :param franken_uinputs: a mapping from device name to the devices uinput object
    :type uinputs: collections.Mapping {device_name: evdev.UInput}
    """
    while(True):
        try:
            device = get_device(config)
            if config.get("exclusive", False):
                with device.grab_context():
                    await asyncio.ensure_future(process_events(device, config["events"], franken_uinputs))
            else:
                await asyncio.ensure_future(process_events(device, config["events"], franken_uinputs))
        except NoDeviceError as e:
            logger.error(str(e))
            await asyncio.sleep(10)


async def process_events(device, config, franken_uinputs):
    """
    Translate events from a source input device to a target uinput device.
    :param device: the source input device
    :type device: evdev.InputDevice
    :param config: the configuration for the source device (from the yaml)
    :type config: collections.Mapping
    :param franken_uinputs: the uinput device to send events to
    :type franken_uinputs: collections.Mapping {device_name: evdev.UInput}
    """
    logger.info(f"Processing events from {device.path} {device.name}")
    hooked_uinputs = []
    for event_code_config in config.values():
        for franken_device_name in event_code_config.keys():
            hooked_uinputs.append(franken_uinputs[franken_device_name])

    absinfos = dict(device.capabilities(absinfo=True)[evdev.ecodes.EV_ABS])
    franken_absinfos = {
        n: dict(d.capabilities(absinfo=True)[evdev.ecodes.EV_ABS])
        for n, d in franken_uinputs.items()
    }

    async for event in device.async_read_loop():
        # TODO raise a NoDeviceError if the device goes away
        # always pass on sync events
        if event.type == evdev.ecodes.EV_SYN:
            for franken_uinput in hooked_uinputs:
                franken_event(event, franken_uinput, event.code)

            continue

        try:
            event_config = config[event.code]
        except KeyError:
            logger.debug(f"skipping event {device.path}|{event.type}|{event.code}|{evdev.categorize(event)}")
            continue

        for franken_device_name, franken_event_code in event_config.items():
            if event.type == evdev.ecodes.EV_ABS:
                absinfo = absinfos[event.code]
                franken_absinfo = franken_absinfos[franken_device_name][franken_event_code]
            else:
                absinfo = None
                franken_absinfo = None

            franken_event(
                event,
                franken_uinputs[franken_device_name],
                franken_event_code,
                original_absinfo=absinfo,
                franken_absinfo=franken_absinfo,
            )


def franken_event(
        original_event,
        franken_uinput,
        franken_event_code,
        original_absinfo=None,
        franken_absinfo=None):

    event = evdev.InputEvent(
        original_event.sec,
        original_event.usec,
        original_event.type,
        franken_event_code,
        franken_value(original_event.value, original_absinfo, franken_absinfo),
    )
    franken_uinput.write_event(event)
    logger.debug(f"generated event {franken_uinput.device.path} {evdev.categorize(event)} {event.code}")


def franken_value(original_value, original_absinfo, franken_absinfo):
    # if event.type == EV_ABS, shift and scale the value using the absinfo
    # of both devices.
    # For example the source value might range from 0-65536 whereas
    # the output value might range from -32767 to +32767.
    # Could also get fancy and define deadzones and curves in config, but
    # let's not for now.
    if original_absinfo is None:
        return original_value

    normalized = (original_value - original_absinfo.min) / (original_absinfo.max - original_absinfo.min)
    return int(normalized * (franken_absinfo.max - franken_absinfo.min) + franken_absinfo.min)


def button(uinput, code, value=1, syn=True):
    """
    Send a button event.
    :param uinput: the uinput device to generate the button event
    :type uinput: evdev.UInput
    :param code: the event code, e.g. evdev.ecodes.BTN_A
    :type code: int
    :param value: 1 (button down), 0 (button up)
    :type code: int
    :param syn: whether or not to follow up the event with a syn event
    :type syn: bool
    """
    # sec and usec are thrown out anyway, see
    # https://github.com/gvalkov/python-evdev/blob/master/evdev/eventio.py#L111
    uinput.write_event(evdev.InputEvent(0, 0, evdev.ecodes.EV_KEY, code, value))
    if(syn):
        uinput.syn()


def button_toggle(uinput, code):
    """
    Send a button down event, followed a short time later by a button up event.
    :param uinput: the uinput device to generate the button event
    :type uinput: evdev.UInput
    :param code: the event code, e.g. evdev.ecodes.BTN_A
    :type code: int
    """
    button(uinput, code, value=1)
    time.sleep(0.2)
    button(uinput, code, value=0)


def make_franken_uinputs(config):
    def make_uinput(name, device_config):
        # either predefined or custom
        try:
            capabilities = frankengamepad.config.PREDEFINED_CAPABILITIES[device_config["type"]]
        except KeyError:
            capabilities = {}  # TODO based on device_config["type"]["capabilities"]

        capabilities = {k: v for k, v in capabilities.items()
                if k not in {evdev.ecodes.EV_SYN, evdev.ecodes.EV_FF}}
        # Could set vendor etc but some games don't like it
        return evdev.UInput(capabilities, name=name)

    frankens = {k: make_uinput(k, v) for k, v in config.items()}
    for name, uinput in frankens.items():
        logger.info(f"Created {name} at {uinput.device.path}")

    return frankens


def run_translations(config, franken_uinputs):
    """
    Using the frankegamepad configuration (from the yaml), watch devices, listen
    to their events, and translate them to the franken gamepads.
    This method will block forever until SIGINT or SIGTERM is received.
    :param config: The sources configuration from the yaml
    :type config: collections.Mapping
    :param franken_uinputs: A mapping of uinput devices for franken gamepads
    :type franken_uinputs: collections.Mapping {device_name: evdev.UInput}
    """
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    asyncio.gather(*(watch_device(source, franken_uinputs) for source in config.values()))
    loop.run_forever()
