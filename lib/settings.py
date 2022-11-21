import json
import logging
import sys

logger = logging.getLogger('main2.settings')
DEFAULT_CONFIG = 'config.json'


class Settings:
    __slots__ = (
        "output_directory",
        "categories",
        "delay_range",
        "max_retries",
        "headers",
        "logs_dir",
        "restart",
        "provided"
    )

    def __init__(self):
        try:
            config = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
            settings = json.load(open(config, 'r'))

            for key, value in settings.items():
                setattr(self, key, value)
            self.provided = True

        except FileNotFoundError as e:
            logger.error('Config argument found, but no such file found. Exception: ', e)
