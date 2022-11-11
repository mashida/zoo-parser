import json
import sys


class Settings:
    __slots__ = (
        "output_directory",
        "categories",
        "delay_range",
        "max_retries",
        "headers",
        "logs_dir",
        "restart"
    )

    def __init__(self):
        try:
            config = sys.argv[1]
            settings = json.load(open(config, 'r'))

            for key, value in settings.items():
                setattr(self, key, value)

        except IndexError as e:
            print('No config file found. Exception:', e)

        except FileNotFoundError as e:
            print('Config argument found, but no such file found. Exception: ', e)
