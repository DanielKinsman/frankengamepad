import click
import logging
import sys
from . import setup_logging
from . import config as fconfig
from . import device as fdevice


logger = logging.getLogger(__name__)


@click.command()
@click.option("--config-file", default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="A yaml configuration file describing gamepad mappings.")
@click.option("--log-file", default=None,
        type=click.Path(dir_okay=False, resolve_path=True),
        help="File to store the log in.")
@click.option("--interactive", is_flag=True,
        help="Creates virtual gamepads then launches an interactive "
        "python prompt before beginning to map input devices to output "
        "devices. Useful for games you need to start with only the "
        "virtual gamepad before doing anything else.")
def main(config_file, log_file, interactive):
    setup_logging(log_file)

    if config_file is None:
        config_file=fconfig.default_config_file()

    logger.info(f"loading config from `{config_file}`")
    config = fconfig.load(config_file)
    franken_uinputs = fdevice.make_franken_uinputs(config["outputs"])
    if interactive:
        from . import interactive
        interactive.session(franken_uinputs)

    fdevice.run_translations(config["sources"], franken_uinputs)
    sys.exit(0)
