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


async def process_events(device, config):
    async for event in device.async_read_loop():
        print(device.path, evdev.categorize(event), sep=': ')


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


@click.command()
@click.argument("config_file", default=default_config_file(),
    type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("--logfile", default=None, type=click.Path(dir_okay=False, resolve_path=True))
def main(config_file, logfile):
    setup_logging(logfile)

    if config_file is None:
        config_file = default_config_file()

    config = load_config(config_file)

    # config now looks like this:

    #   {
    #       sources:
    #       {
    #           usbgamepad:
    #           {
    #               "name": "usb gamepad",
    #               "exclusive": True
    #               "events": {
    #                   0: {
    #                       "frankengamepadzero": 0,
    #                   }
    #           },
    #       }
    #   }

    all_devices = (evdev.InputDevice(p) for p in evdev.list_devices())
    all_devices = {d.name: d for d in all_devices}

    # TODO create franken devices

    grabbed = []
    try:
        for source in config["sources"].values():
            try:
                device  = all_devices[source["name"]]
            except KeyError:
                raise KeyError(f"Could not find device `{source['name']}`")

            if source["exclusive"]:
                device.grab()
                grabbed.append(device)
                logger.info(f"Grabbed exclusive access to {device.path}")

            asyncio.ensure_future(process_events(device, source["events"]))
        loop = asyncio.get_event_loop()
        loop.run_forever()
    finally:
        for d in grabbed:
            d.ungrab()
            logger.info(f"Released exclusive access to {d.path}")

    sys.exit(0)
