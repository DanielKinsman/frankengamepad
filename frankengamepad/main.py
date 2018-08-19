import asyncio
import click
import collections
import evdev
import logging
import os
import sys
import yaml


DEFAULT_CONFIG = {
    "sources": {},
    "outputs": {},
}

PREDEFINED_CAPABILITIES = {
    # To generate these, connect and load the device for reading then use
    # `evdev.InputDevice.capabilities()`
    "xbox360":
    {
	0: [0, 1, 3, 21],
	1:
        [
            304,
	    305,
            307,
            308,
            310,
            311,
            314,
            315,
            316,
            317,
            318,
            704,
            705,
            706,
            707,
        ],
        3:
        [
            (0, evdev.device.AbsInfo(value=-2687, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
            (1, evdev.device.AbsInfo(value=-5789, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
            (2, evdev.device.AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
            (3, evdev.device.AbsInfo(value=496, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
            (4, evdev.device.AbsInfo(value=-2833, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
            (5, evdev.device.AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
            (16, evdev.device.AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
            (17, evdev.device.AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        ],
        21: [80, 81, 88, 89, 90, 96]
    }
}


logger = logging.getLogger(__name__)


def setup_logging(logfile):
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(asctime)s:%(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if logfile is not None:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Writing log to {logfile}")


def config_dir():
    default_config_home = os.path.join(os.environ["HOME"], ".config")
    config_home = os.getenv("XDG_CONFIG_HOME", default_config_home)
    config_dir = os.path.join(config_home, "frankengamepad")
    if not os.path.exists(config_dir):
        logger.info(f"{config_dir} does not exist, creating it")
        os.mkdir(config_dir)

    return config_dir


def default_config_file():
    default = os.path.join(config_dir(), "default.yaml")
    if not os.path.exists(default):
        logger.info(f"{default} does not exist, creating it")
        with open(default, "wt") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f);

    return default


async def process_events(device, config, franken_uinputs):
    hooked_uinputs = []
    for event_code_config in config.values():
        for franken_device_name in event_code_config.keys():
            hooked_uinputs.append(franken_uinputs[franken_device_name])

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
            franken_event(
                event,
                franken_uinputs[franken_device_name],
                franken_event_code,
            )

def franken_event(original_event, franken_uinput, franken_event_code):
    event = evdev.InputEvent(
        original_event.sec,
        original_event.usec,
        original_event.type,
        franken_event_code,
        original_event.value
    )
    franken_uinput.write_event(event)
    logger.debug(f"generated event {franken_uinput.device.path} {evdev.categorize(event)} {event.code}")


def load_config(config_file):
    with open(config_file, "rt") as f:
        config = yaml.safe_load(f)

    def replace_keys_and_values(mapping):
        def replace(value):
            try:
                return getattr(evdev.ecodes, value, value)
            except TypeError:
                return value  # value wasn't a string so getattr complained

        new_mapping = {}
        for k, v in mapping.items():
            if isinstance(v, collections.Mapping):
                new_mapping[replace(k)] = replace_keys_and_values(v)
            else:
                new_mapping[replace(k)] = replace(v)

        return new_mapping

    return replace_keys_and_values(config)


def make_franken_uinputs(config):
    def make_uinput(name, device_config):
        # either predefined or custom
        try:
            capabilities = PREDEFINED_CAPABILITIES[device_config["type"]]
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

            if source["exclusive"]:
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


@click.command()
@click.argument("config_file", default=default_config_file(),
    type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("--logfile", default=None, type=click.Path(dir_okay=False, resolve_path=True))
def main(config_file, logfile):
    setup_logging(logfile)

    if config_file is None:
        config_file = default_config_file()

    config = load_config(config_file)
    franken_uinputs = make_franken_uinputs(config["outputs"])
    run_translations(config["sources"], franken_uinputs)
    sys.exit(0)
