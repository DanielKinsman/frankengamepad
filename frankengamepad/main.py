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


def config_dir():
    default_config_home = os.path.join(os.environ["HOME"], ".config")
    config_home = os.getenv("XDG_CONFIG_HOME", default_config_home)
    config_dir = os.path.join(config_home, "frankengamepad")
    if not os.path.exists(config_dir):
        logging.info(f"{config_dir} does not exist, creating it")
        os.mkdir(config_dir)

    return config_dir


def default_config_file():
    default = os.path.join(config_dir(), "default.yaml")
    if not os.path.exists(default):
        logging.info(f"{default} does not exist, creating it")
        with open(default, "wt") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f);

    return default


async def print_events(device, mappings):
    async for event in device.async_read_loop():
        print(device.path, evdev.categorize(event), sep=': ')


def make_mappings(config):
    """
    config looks like this:

        {
            "name": "usb gamepad",
            "exclusive": True
            "events": {
                "ABS_X": {
                    "frankengamepadzero": "ABS_X",
                }
        }

    """
    for event, franken_devices in config["events"].items():
        for franken_device, franken_event in franken_devices.items():
            yield (config["name"], event, franken_device, franken_event)


@click.command()
@click.argument("config_file", default=default_config_file(),
    type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def main(config_file):
    if config_file is None:
        config_file = default_config_file()

    with open(config_file, "rt") as f:
        config = yaml.safe_load(f)
        
    # config looks like this:

    #   {
    #       sources:
    #       {
    #           usbgamepad:
    #           {
    #               "name": "usb gamepad",
    #               "exclusive": True
    #               "events": {
    #                   "ABS_X": {
    #                       "frankengamepadzero": "ABS_X",
    #                   }
    #           },
    #       }
    #   }

    all_devices = (evdev.InputDevice(p) for p in evdev.list_devices())
    all_devices = {d.name: d for d in all_devices}
    
    devices = {}
    mappings = collections.defaultdict(dict)
    for source in config["sources"].values():
        if source["name"] not in all_devices:
            raise ValueError(f"Could not find {source['name']} in devices")

        devices[source["name"]] = all_devices[source["name"]]

        for device_name, event, franken_device_name, franken_event in make_mappings(source):
            mappings[device_name][event] = (franken_device_name, franken_event)

    for device_name, device in devices.items():
        asyncio.ensure_future(print_events(device, mappings[device_name]))
    
    loop = asyncio.get_event_loop()
    loop.run_forever()

    sys.exit(0)
