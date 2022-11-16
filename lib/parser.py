import csv
from pathlib import Path
from random import uniform
from time import sleep

import requests
from bs4 import BeautifulSoup
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from lib.category import Category
from lib.helper import tags
from lib.product import Product
from lib.settings import Settings

ZOO_URL = 'https://zootovary.ru'
CATALOG = '/catalog/'

headers = ['name', 'id', 'parent_id', 'link']


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
        self.required_categories_list = []
        self.required_categories_provided: bool = False
        self.products_list_by_category: dict[str, list] = {}
        self.parsed_articles_list: list[str] = []
        self.parsed_barcodes_list: list[str] = []
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
        self.all_categories_parsed_tree: Category = Category()
        self.required_categories_parsed_list: list[Category] = []
        #
        self.apply_config(settings=settings)

    def apply_config(self, settings: Settings) -> None:
        if not settings.provided:
            return
        self.out_dir = Path(settings.output_directory)
        self.logs_dir = settings.logs_dir
        self.max_retries = settings.max_retries
        self.headers = settings.headers
        self.delay_range = settings.delay_range
        self.restart = settings.restart
        self.required_categories_list = [CATALOG] if len(settings.categories) == 0 else settings.categories
        self.required_categories_provided = True if len(settings.categories) > 0 else False

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
                self.amount_of_pages[catalog_url] = len([x for x in tags(navigation_links)])
        logger.info(f'        We found {self.amount_of_pages[catalog_url]} pages and {count_products} products '
                    f'on a first page of category: {catalog_url}')

    def parse_all_categories(self):
        logger.info('Parsing all categories..')
        if self.all_categories_are_parsed:
            logger.warning(f'Categories have been parsed already. Skipping...')
            return

        self.all_categories_parsed_tree = Category(url=ZOO_URL + CATALOG, base_url=ZOO_URL, link=CATALOG, code=0,
                                                   stage=0)
        self.all_categories_are_parsed = True
        logger.info('Done | all categories passed')

    def parse_category_out_of_url(self, category_url: str):
        index = self.required_categories_list.index(category_url) + 1
        logger.info(f'    {index}/{len(self.required_categories_list)} Parsing {category_url} category out of url')
        if self.required_categories_provided:
            self.required_categories_parsed_list.append(
                self.all_categories_parsed_tree.get_by_link(link=category_url, stage=1))
        logger.info(f'    Done')

    @staticmethod
    def parse_block(item):
        data = item.select_one('a.name')
        return [data['href'], data['title']]

    def get_all_products_links_out_of_category(self, catalog_url: str = None):
        if self.amount_of_pages[catalog_url] == 0:
            self.products_list_by_category[catalog_url] = []
            return
        for page in range(1, self.amount_of_pages[catalog_url] + 1):
            params = {'pc': 50, 'v': 'filling', 'PAGEN_1': page}
            soup = self.get_soup_out_of_page_with_url(ZOO_URL + catalog_url, params=params)
            catalog_info = soup.select('div.catalog-content-info')
            for item in catalog_info:
                product = Product(*self.parse_block(item=item))
                if catalog_url not in self.products_list_by_category.keys():
                    self.products_list_by_category[catalog_url] = []
                self.products_list_by_category[catalog_url].append(product)
        logger.info(f'        We have found {len(self.products_list_by_category[catalog_url])} products to parse')

    def parse_all_products_out_of_category(self, catalog_url: str = None):
        logger.info(f'        Starting to parse products of {catalog_url} category')
        for index, product in enumerate(self.products_list_by_category[catalog_url], start=1):
            if product.parsed:
                logger.warning(f"We already parsed this product: [{product['title']}|{product['href']}]")
                continue
            index = f'{index}/{len(self.products_list_by_category[catalog_url])}'
            product.parse(articles=self.parsed_articles_list, barcodes=self.parsed_barcodes_list, index=index)
        logger.info(f'        Done | Products from {catalog_url} have been parsed')

    def parse_cards(self, catalog_url):
        logger.info(f'      Parsing cards out of {catalog_url}')
        soup = self.get_soup_out_of_page_with_url(ZOO_URL + catalog_url, params={'pc': 50, 'v': 'filling'})
        self.calc_amount_of_pages(soup=soup, catalog_url=catalog_url)
        # let's get links of all products in this category
        self.get_all_products_links_out_of_category(catalog_url=catalog_url)
        # let's parse all products we have within this category
        self.parse_all_products_out_of_category(catalog_url=catalog_url)

    def csv_write(self):
        self.out_dir.mkdir(exist_ok=True)
        # write all categories
        with (self.out_dir / 'categories-all.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            temp = [item for item in self.all_categories_parsed_tree.list_of_children()]
            for cat in temp:
                writer.writerow(cat)
        # write categories

        with (self.out_dir / 'categories.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for category in self.required_categories_parsed_list:
                temp_list = [item for item in category.list_of_children()]
                for cat in temp_list:
                    writer.writerow(cat)
        # write goods
        goods_headers = (
            'price_datetime', 'price', 'price_promo', 'sku_status', 'sku_barcode', 'sku_article', 'sku_name',
            'sku_category', 'sku_country', 'sku_weight_min', 'sku_volume_min', 'sku_quantity_min', 'sku_link',
            'sku_images')
        with (self.out_dir / 'goods.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(goods_headers)
            for category in self.required_categories_list:
                for product in self.products_list_by_category[category]:
                    writer.writerow(product.to_csv)

    def work(self):
        for _ in range(self.restart['restart_count']):
            try:
                self.parse_all_categories()
                logger.info(f'We have {len(self.required_categories_list)} categories to parse..')
                for url in self.required_categories_list:
                    logger.info(f'  Parsing {url} category')
                    self.parse_category_out_of_url(url)
                    self.parse_cards(url)
                    logger.info(f'  Done | Category {url} parsed')
                break
            except KeyboardInterrupt as e:
                logger.error('Stopping by keyboard interruption.')
                break
            except BaseException as e:
                logger.error(f'Error occurred: {e}')
                sleep(self.restart['interval_m'] * 60)


