import asyncio
import evdev
import logging
import time
import frankengamepad.config


logger = logging.getLogger(__name__)


async def process_events(device, config, franken_uinputs):
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
                franken_absinfo = franken_absinfos[franken_device_name][franken_event_code],
            else:
                absinfo = None
                franken_absinfo = None,

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
    :param franken_uinput: the evdev.UInput device to generate the button event
    :param code: the event code, e.g. evdev.ecodes.BTN_A
    :param value: 1 (button down), 0 (button up)
    """
    # sec and usec are thrown out anyway, see
    # https://github.com/gvalkov/python-evdev/blob/master/evdev/eventio.py#L111
    uinput.write_event(evdev.InputEvent(0, 0, evdev.ecodes.EV_KEY, code, value))
    if(syn):
        uinput.syn()


def button_toggle(uinput, code):
    button(uinput, code, value=1)
    time.sleep(0.1)
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
        return evdev.UInput(capabilities, name=name)

    frankens = {k: make_uinput(k, v) for k, v in config.items()}
    for name, uinput in frankens.items():
        logger.info(f"Created {name} at {uinput.device.path}")

    return frankens


def run_translations(config, franken_uinputs):
    all_devices = (evdev.InputDevice(p) for p in evdev.list_devices())
    all_devices = {d.name: d for d in all_devices}

    grabbed = []
    try:
        for source in config.values():
            try:
                device  = all_devices[source["name"]]
            except KeyError:
                raise KeyError(f"Could not find device `{source['name']}`")

            if source.get("exclusive", False):
                device.grab()
                grabbed.append(device)
                logger.info(f"Grabbed exclusive access to {device.path}")

            asyncio.ensure_future(process_events(device, source["events"], franken_uinputs))

        loop = asyncio.get_event_loop()
        loop.run_forever()
    finally:
        for d in grabbed:
            d.ungrab()
            logger.info(f"Released exclusive access to {d.path}")
