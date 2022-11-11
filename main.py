import requests
from bs4 import BeautifulSoup, Tag
from lib.settings import Settings
from collections import namedtuple
import csv
import logging
import datetime
from time import sleep
from random import uniform
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path

ZOO_URL = 'https://zootovary.ru'
CATALOG = '/catalog/'

category_list = []
goods_list = []
ready_goods_list = []
barcodes = []
articles = []

Category = namedtuple('Top', 'title, url, link, id, parent_id')
Good = namedtuple('Good', 'price_datetime, price, price_promo, sku_status, sku_barcode, sku_article, sku_name,'
                          'sku_category, sku_country, sku_weight_min, sku_volume_min, sku_quantity_min, sku_link,'
                          'sku_images')

headers = ['name', 'id', 'parent_id']
FORMAT = '%(message)s'
path_to_log = f''
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger('Zoo')


def tags(items) -> Tag:
    for item in items:
        if not isinstance(item, Tag):
            continue
        yield item


class Parser:

    def __init__(self):
        self.session = requests.Session()
        self.settings = Settings()
        self.out_dir = Path(self.settings.output_directory)
        self.top = ""
        self.amount_of_pages: int = 0
        self.setup_session()
        self.categories_are_parsed: bool = False

    def setup_session(self):
        retry_strategy = Retry(
            total=self.settings.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(self.settings.headers)

    def run(self):
        if self.categories_are_parsed:
            logger.warning(f'Categories have been parsed already. Skipping...')
            return
        soup = self.get_page_with_url(ZOO_URL + CATALOG, params={'pc': 50, 'v': 'filling'})
        self.get_total_pages(soup)
        tops = soup.find('ul', 'catalog-menu-left-1')  # animal wrappers

        if not tops:
            logger.error(f'No categories found. Exit')
            return

        i = 0
        for top in tags(tops):
            animal = top.find('a', 'item-depth-1')
            i += 1
            animal_code = i * 1000000
            logger.debug(str(animal_code) + ':' + animal['title'] + ' | ' + animal['href'])
            category_list.append(
                Category(title=animal['title'], url=ZOO_URL, link=animal['href'], id=animal_code, parent_id=0))
            #
            h1 = self.get_page_with_url(ZOO_URL + animal['href'])
            categories = h1.find('ul', 'catalog-menu-left-1')  # category wrappers
            if not categories:
                continue
            j = 0
            for category in tags(categories):
                cat = category.find('a', 'item-depth-1')
                j += 1
                cat_code = animal_code + j * 10000
                logger.debug('\t' + str(cat_code) + ':' + cat['title'] + ' | ' + cat['href'])
                category_list.append(Category(title=cat['title'], url=ZOO_URL, link=cat['href'], id=cat_code,
                                              parent_id=animal_code))
                #
                brands = category.find('ul', 'catalog-menu-left-2')  # brands wrapper
                if not brands:
                    continue
                k = 0
                for brand in tags(brands):
                    bra = brand.find('a', 'item-depth-2')
                    k += 1
                    bra_code = cat_code + k * 10
                    logger.debug('\t\t' + str(bra_code) + ':' + bra['title'] + ' | ' + bra['href'])
                    category_list.append(Category(title=bra['title'], url=ZOO_URL, link=bra['href'], id=bra_code,
                                                  parent_id=cat_code))
                    #
                    subs = brand.find('ul', 'catalog-menu-left-3')  # subcategory wrapper
                    if not subs:
                        continue
                    z = 0
                    for sub in tags(subs):
                        z += 1
                        subb = sub.find('a', 'item-depth-3')
                        sub_code = bra_code + z
                        logger.debug('\t\t\t' + str(sub_code) + ':' + subb['title'] + ' | ' + subb['href'])
                        category_list.append(Category(title=subb['title'], url=ZOO_URL, link=subb['href'], id=sub_code,
                                                      parent_id=bra_code))
            logger.debug('*' * 20)
            self.categories_are_parsed = True

    def get_page(self, page: int = None):
        params = {
            'pc': 50,
            'v': 'filling'
        }
        if page and page > 1:
            params['PAGEN_1'] = page

        url = ZOO_URL + CATALOG
        result = self.get_page_with_url(url, params=params)
        return result

    def get_page_with_url(self, url: str, params: dict = None):
        # randomized delay according to settings
        sleep(uniform(self.settings.delay_range[0], self.settings.delay_range[1]))
        result = self.session.get(url, params=params)
        return BeautifulSoup(result.text, 'lxml')

    @staticmethod
    def parse_block(item):
        product = item.select_one('a.name')
        return {'href': product['href'], 'title': product['title']}

    def parse_cards(self):
        # parse pages
        for i in range(1, self.amount_of_pages + 1):
            soup = self.get_page(i)

            # Запрос CSS-селектора для поиска карточек на странице
            container = soup.select('div.catalog-content-info')
            temp_amount = 0
            for item in container:
                block = self.parse_block(item=item)
                temp_amount += 1
                goods_list.append(block)
            logger.info(f'searching page #{i}/{self.amount_of_pages} | {temp_amount} cards saved')

        # parse goods
        for good in goods_list:
            soup = self.get_page_with_url(ZOO_URL + good['href'])
            element = soup.find('div', {'id': 'comp_d68034d8231659a2cf5539cfbbbd3945'})
            price_datetime = datetime.datetime.now()
            #
            price_wrapper = element.find('tr', 'b-catalog-element-offer')
            items = [x for x in tags(price_wrapper)]
            # get article
            sku_article = items[0].contents[3].contents[0] if item_is_valid(items, 0, 3) else ""
            logger.info(f'Артикул: {sku_article}')
            # get barcode
            sku_barcode = items[1].contents[3].contents[0] if item_is_valid(items, 1, 3) else ""
            logger.info(f'Штрих код: {sku_barcode}')
            # if we already have this article or barcode - we skip this good
            if sku_article in articles or sku_barcode in barcodes:
                logger.error(f'we have saved item with artcile {sku_article} or barcode {sku_barcode}')
                continue
            articles.append(sku_article)
            barcodes.append(sku_barcode)
            # get min volume, weight or quantity
            min_value = items[2].contents[3].contents[0] if item_is_valid(items, 2, 3) else ""
            sku_weight_min = get_weight(text=min_value)
            sku_volume_min = get_volume(text=min_value)
            sku_quantuty_min = get_quantity(text=min_value)
            # get price
            price = items[4].contents[4].contents[0] if item_is_valid(items, 4, 4) else ""
            # get promo price
            promo_price = items[4].contents[7].contents[0] if item_is_valid(items, 4, 7) else ""
            # get status
            status = get_status(price_wrapper)
            # get country
            country_wrapper = element.select_one('div.catalog-element-offer-left')
            country = get_country(country_wrapper)
            # get categories
            categories_wrapper = element.select_one('ul.breadcrumb-navigation')
            categories = get_categories(categories_wrapper)
            # get pictures
            pictures_wrapper = element.find_all('div', 'catalog-element-small-picture')
            pictures = get_pictures(pictures_wrapper)
            logger.info(categories)
            logger.info(pictures)
            logger.info(
                f"{good['title']} | {min_value} | weight: {sku_weight_min}, "
                f"volume: {sku_volume_min}, quantity: {sku_quantuty_min}, "
                f"price: {price}, promo_price: {promo_price}, status: {status}, country: {country}")

            #  'price_datetime, price, price_promo, sku_status, sku_barcode, sku_article, sku_name,'
            #  'sku_category, sku_country, sku_weight_min, sku_volume_min, sku_quantity_min, sku_link,'
            #  'sku_images')

            ready_goods_list.append(
                Good(price_datetime, price, promo_price, status, sku_barcode, sku_article, good['title'],
                     categories, country, sku_weight_min, sku_volume_min, sku_quantuty_min, good['href'],
                     pictures))
            logger.info('-' * 30)

    def get_total_pages(self, soup) -> None:
        navigations = soup.find('div', {'class': 'navigation'})

        for navi in tags(navigations):
            if navi.getText() == '»':
                href = navi['href']
                splits = href.split('=')
                self.amount_of_pages = int(splits[len(splits) - 1])
                logger.info(f'{self.amount_of_pages} pages found..')
                return
        raise Exception("We couldn't find the '»' symbol at the main page, so no total amount of pages")

    def work(self):
        for _ in range(self.settings.restart['restart_count']):
            try:
                self.run()
                self.parse_cards()
                break
            except BaseException as e:
                logger.error('Error occured: {e}')
                sleep(self.settings.restart['interval_m'] * 60)
                continue

    def csv_write(self):
        # write categories
        self.out_dir.mkdir(exist_ok=True)
        with (self.out_dir / 'categories.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for cat in category_list:
                writer.writerow((cat.title, cat.id, cat.parent_id))
        # write goods
        goods_headers = (
            'price_datetime', 'price', 'price_promo', 'sku_status', 'sku_barcode', 'sku_article', 'sku_name,'
                                                                                                  'sku_category',
            'sku_country', 'sku_weight_min', 'sku_volume_min', 'sku_quantity_min', 'sku_link,'
                                                                                   'sku_images')
        with (self.out_dir / 'goods.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(goods_headers)
            for good in ready_goods_list:
                writer.writerow(good)


def get_one_out_of_list(text: str, lst: list) -> str:
    result = ""
    for mera in lst:
        if mera in text:
            result = text if len(text.split(mera)[0]) > 0 else ""
            break
    return result


def get_weight(text) -> str:
    return get_one_out_of_list(text, ['кг', 'гр', 'г'])


def get_volume(text) -> str:
    return get_one_out_of_list(text, ['л'])


def get_quantity(text) -> str:
    return get_one_out_of_list(text, ['шт'])


def item_is_valid(item, i, j):
    return len(item[i].contents) > j - 1 and isinstance(item[i].contents[j], Tag) and item[i].contents[j].contents


def get_status(p_wrapper):
    return 1 if p_wrapper.find('div', 'catalog-item-no-stock') is None else 0


def get_country(c_wrapper):
    return c_wrapper.contents[3].contents[0].split(':')[1].strip() if len(c_wrapper.contents) > 3 and len(
        c_wrapper.contents[3].contents) > 0 else ""


def get_categories(category_wrapper):
    categs = []
    for i in range(4, len(category_wrapper.contents) - 2, 2):
        name = category_wrapper.contents[i].contents[0].getText()
        categs.append(name)

    return '|'.join(categs)


def get_pictures(picture_wrapper) -> str:
    links = []
    for picture in picture_wrapper:
        if 'href' in picture.contents[1].attrs.keys():
            links.append(ZOO_URL + picture.contents[1].attrs['href'])
    return ', '.join(links)


def main():
    parser = Parser()
    parser.work()
    parser.csv_write()


if __name__ == "__main__":
    main()
