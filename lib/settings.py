import json
import logging
import sys

logger = logging.getLogger('main2.settings')


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
            if len(sys.argv) > 1:
                config = sys.argv[1]
                settings = json.load(open(config, 'r'))

                for key, value in settings.items():
                    setattr(self, key, value)
                self.provided = True
            else:
                logger.info(f'No config file provided, using default values...')
                self.provided = False

        except FileNotFoundError as e:
            logger.error('Config argument found, but no such file found. Exception: ', e)
