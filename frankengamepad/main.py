import click
import logging
import sys
from . import config as fconfig
from . import device as fdevice

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


@click.command()
@click.argument("config_file", default=fconfig.default_config_file(),
    type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("--logfile", default=None, type=click.Path(dir_okay=False, resolve_path=True))
@click.option("--interactive", is_flag=True)
def main(config_file, logfile, interactive):
    setup_logging(logfile)

    logger.info(f"loading config from `{config_file}`")
    config = fconfig.load(config_file)
    franken_uinputs = fdevice.make_franken_uinputs(config["outputs"])
    if interactive:
        from . import interactive
        interactive.session(franken_uinputs)

    fdevice.run_translations(config["sources"], franken_uinputs)
    sys.exit(0)
