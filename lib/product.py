from collections import namedtuple

from loguru import logger
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from lib.helper import tags

ZOO_URL = 'https://zootovary.ru'
CATALOG = '/catalog/'

Offer = namedtuple('Offer', 'sku_article, sku_barcode, min_value, sku_weight_min, sku_volume_min, sku_quantity_min,'
                            'price, promo_price, status')


def get_page_with_url(url: str):
    # randomized delay according to settings
    params = {'pc': 50, 'v': 'filling'}
    # sleep(uniform(self.delay_range[0], self.delay_range[1]))
    result = requests.get(url, params=params)
    return BeautifulSoup(result.text, 'lxml')


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


class Product:
    def __init__(self, href: str = None, title: str = None, parsed: bool = False):
        self.href = href
        self.title = title
        self.parsed = parsed
        self.price_datetime: str = ''
        self.offers: list[Offer] = []
        self.country: str = ''
        self.categories: str = ''
        self.pictures: str = ''

    def parse(self, articles: list[str], barcodes: list[int], index: str = ""):
        # get the soup from link of the product
        soup = get_page_with_url(ZOO_URL + self.href)
        element = soup.find('div', {'id': 'comp_d68034d8231659a2cf5539cfbbbd3945'})
        if element is None:
            logger.error(f"we've got no data from {self.href}, skipping")
            return
        self.price_datetime = datetime.now()
        # оказывается в карточке есть несколько предложений » offers table
        offers_soup = element.find('table', 'b-catalog-element-offers-table')
        for offer in tags(offers_soup):
            #
            # price_content = element.find('tr', 'b-catalog-element-offer')
            items = [x for x in tags(offer)]
            # get article
            sku_article = items[0].contents[3].contents[0] if item_is_valid(items, 0, 3) else ""
            # logger.info(f'Артикул: {sku_article}')
            # get barcode
            sku_barcode = items[1].contents[3].contents[0] if item_is_valid(items, 1, 3) else ""
            # logger.info(f'Штрих код: {sku_barcode}')
            # if we already have this article or barcode - we skip this good
            if sku_article in articles or sku_barcode in barcodes:
                logger.error(f'we have saved item with article {sku_article} or barcode {sku_barcode}')
                return

            articles.append(sku_article)
            barcodes.append(sku_barcode)
            # get min volume, weight or quantity
            min_value = items[2].contents[3].contents[0] if item_is_valid(items, 2, 3) else ""
            sku_weight_min = get_weight(text=min_value)
            sku_volume_min = get_volume(text=min_value)
            sku_quantity_min = get_quantity(text=min_value)
            # get price
            price = items[4].contents[4].contents[0].strip(' р') if item_is_valid(items, 4, 4) else ""
            # get promo price
            promo_price = items[4].contents[7].contents[0].strip(' р') if item_is_valid(items, 4, 7) else ""
            # get status
            status = get_status(offer)
            # 'sku_article, sku_barcode, min_value, sku_weight_min, sku_volume_min, sku_quantity_min,'
            # 'price, promo_price, status'
            self.offers.append(Offer(sku_article, sku_barcode, min_value, sku_weight_min, sku_volume_min,
                                     sku_quantity_min, price, promo_price, status))
        # get country
        country_wrapper = element.select_one('div.catalog-element-offer-left')
        self.country = get_country(country_wrapper)
        # get categories
        categories_wrapper = element.select_one('ul.breadcrumb-navigation')
        self.categories = get_categories(categories_wrapper)
        # get pictures
        pictures_wrapper = element.find_all('div', 'catalog-element-small-picture')
        self.pictures = get_pictures(pictures_wrapper)
        self.parsed = True
        #
        self.print_with_index(index)

    def print_with_index(self, index: str):
        logger.info(f'{index} {self.first_line}')
        for offer in self.offers:
            logger.info(f'{" " * len(index)} {self.second_line(offer)}')

    @property
    def to_csv(self):
        for offer in self.offers:
            yield tuple([self.price_datetime, offer.price, offer.promo_price, offer.status, offer.sku_barcode,
                         offer.sku_article, self.title, self.categories, self.country, offer.sku_weight_min,
                         offer.sku_volume_min, offer.sku_quantity_min, ZOO_URL + self.href, self.pictures])

    @property
    def first_line(self):
        return f'{self.categories} | {self.title} | country: {self.country}'

    @staticmethod
    def second_line(offer: Offer):
        return f'status: {offer.status} | article: {offer.sku_article} | ' \
               f'barcode: {offer.sku_barcode} | price: {offer.price} | promo_price: {offer.promo_price}'


def main():
    title = 'ТитБит Колбаска с легким говяжьим 20гр'
    href = '/catalog/tovary-i-korma-dlya-sobak/titbit-kolbaska-s-legkim-govyazhim-20gr.html'
    product = Product(title=title, href=href)
    product.parse(articles=[], barcodes=[])
    print(product)


if __name__ == "__main__":
    main()
