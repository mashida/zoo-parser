import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

from lib.parser import Parser
from lib.settings import Settings


def set_logging_file(parser: Parser):
    log_file_dir = Path(parser.logs_dir)
    log_file_dir.mkdir(exist_ok=True)
    logfile_name = log_file_dir / f'log-{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.log'
    logfile_error_name = log_file_dir / f'log-{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}-errors.log'
    logger.remove(0)
    logger.add(sink=sys.stdout, level='INFO', format='{message}')
    logger.add(sink=logfile_name, encoding='utf-8', level='INFO', format='{time:YYYY-MM-DD HH:mm:ss.SSS} » {message}')
    logger.add(sink=logfile_error_name, encoding='utf-8', level='ERROR', format='{time:YYYY-MM-DD HH:mm:ss.SSS} » {message}')


def main():
    settings = Settings()
    parser = Parser(settings=settings)
    set_logging_file(parser=parser)
    parser.setup_session()
    parser.work()
    parser.csv_write()


if __name__ == "__main__":
    main()
