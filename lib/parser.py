import logging
# from collections import namedtuple
from pathlib import Path
from random import uniform
from time import sleep

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from lib.settings import Settings
from lib.helper import tags
from lib.category import Category

ZOO_URL = 'https://zootovary.ru'
CATALOG = '/catalog/'


# Category = namedtuple('Category', 'title, url, link, id, parent_id')


class Parser:
    def __init__(self, settings: Settings):
        self.session = requests.Session()
        self.amount_of_pages: dict[str, int] = {}
        self.categories_are_parsed: dict[str, bool] = {}
        self.all_categories_are_parsed: bool = False
        # config parameters
        self.out_dir = Path('out')
        self.logs_dir = Path('logs')
        self.max_retries = 0
        self.categories = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/104.0.5112.124 YaBrowser/22.9.5.710 Yowser/2.5 Safari/537.36",
            "Accept-Language": "ru"
        }
        self.delay_range = [0, 0]
        self.restart = {
            "restart_count": 3,
            "interval_m": 0.2
        }
        # list of all categories parsed
        self.category_list: Category = Category()
        self.required_categories: list[Category] = []
        #
        self.apply_config(settings=settings)

    def apply_config(self, settings: Settings) -> None:
        if not settings.provided:
            return
        self.out_dir = Path(settings.output_directory)
        self.logs_dir = settings.logs_dir
        self.max_retries = settings.max_retries
        self.categories = settings.categories
        self.headers = settings.headers
        self.delay_range = settings.delay_range
        self.restart = settings.restart
        self.categories = [CATALOG] if len(settings.categories) == 0 else settings.categories

    def setup_session(self) -> None:
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(self.headers)

    def get_soup_out_of_page_with_url(self, url: str, params: dict = None) -> BeautifulSoup:
        # randomized delay according to settings
        sleep(uniform(self.delay_range[0], self.delay_range[1]))
        # get soup out of page
        result = self.session.get(url, params=params)
        return BeautifulSoup(result.text, 'lxml')

    def calc_amount_of_pages(self, soup, catalog_url: str = "") -> None:
        # we load each page with 50 foods displayed on it according to parameter 'pc': 50 of the page request
        # in order to find the latest possible page we need to understand do we have more than 50 goods in a category
        #
        # if yes than we may have more than 1 page, and we'll find at list one link in the navigation area
        #   here we either look for '»' symbol (if we have more than 10 pages) or
        #   saving the amount of navigation links (if we have more than 10 pages)
        # if no than we must check if we have any goods to display
        #   if we have 0 goods -> we have 0 pages to analyze
        #   if we have more than 0 goods -> we have 1 page to display
        count_products = len(soup.select('div.catalog-item'))
        if count_products == 0:
            self.amount_of_pages[catalog_url] = 0
        elif 0 < count_products < 50:
            self.amount_of_pages[catalog_url] = 1
        else:
            navigation_links = soup.find('div', {'class': 'navigation'})
            for navi in tags(navigation_links):
                if navi.getText() == '»':
                    href = navi['href']
                    splits = href.split('=')
                    self.amount_of_pages[catalog_url] = int(splits[len(splits) - 1])
            else:
                self.amount_of_pages[catalog_url] = int(len(navigation_links))
        logging.info(f'We found {self.amount_of_pages[catalog_url]} pages and {count_products} products '
                     f'on a first page of category: {catalog_url}')

    def parse_all_categories(self):
        if self.all_categories_are_parsed:
            logging.warning(f'Categories have been parsed already. Skipping...')
            return

        # now we'll look down to the category link in order to create its tree
        # each category consists of 4 elements: top-category, category, brand, sub-category
        # example
        # tovary-i-korma-dlya-sobak - top category
        # tovary-i-korma-dlya-sobak/korm-sukhoy/ - this is a category
        # tovary-i-korma-dlya-sobak/korm-sukhoy/advance_1 - brand
        # tovary-i-korma-dlya-sobak/korm-sukhoy/advance_1/shchenki_1/ - sub-category

        self.category_list = Category(url=ZOO_URL + CATALOG, base_url=ZOO_URL, link=CATALOG, code=0, stage=0)
        self.all_categories_are_parsed = True

    def parse_category_out_of_url(self, category_url: str):
        self.required_categories.append(self.category_list.get_by_link(link=category_url, stage=1))

    def work(self):
        for _ in range(self.restart['restart_count']):
            try:
                self.parse_all_categories()
                for url in self.categories:
                    self.parse_category_out_of_url(url)
                    # self.parse_categories_out_of_url(catalog_url=url)
                    # self.parse_cards(url, self.categories.index(url) + 1)
                break
            except BaseException as e:
                logging.error(f'Error occurred: {e}')
                sleep(self.restart['interval_m'] * 60)
                continue
