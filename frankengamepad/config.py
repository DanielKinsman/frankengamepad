import collections
import evdev
import logging
import os
import yaml


logger = logging.getLogger(__name__)

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


def load(config_file):
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
