import requests
from bs4 import BeautifulSoup
from loguru import logger
from time import sleep

from lib.helper import tags

STAGES = {
    0: {'catalog':
        {'tag': 'ul', 'class': 'catalog-menu-left-1'}, 'item': {'tag': 'a', 'class': 'item-depth-1'},
        'multiplier': 1000000, 'indent': '', 'stop': False},
    1: {'catalog':
        {'tag': 'ul', 'class': 'catalog-menu-left-1'}, 'item': {'tag': 'a', 'class': 'item-depth-1'},
        'multiplier': 10000, 'indent': '\t', 'stop': False},
    2: {'catalog':
        {'tag': 'ul', 'class': 'catalog-menu-left-2'}, 'item': {'tag': 'a', 'class': 'item-depth-2'},
        'multiplier': 10, 'indent': '\t\t', 'stop': False},
    3: {'catalog':
        {'tag': 'ul', 'class': 'catalog-menu-left-3'}, 'item': {'tag': 'a', 'class': 'item-depth-3'},
        'multiplier': 1, 'indent': '\t\t\t', 'stop': False},
    4: {'indent': '\t\t\t\t', 'stop': True}
}


def get_page_with_url(url: str):
    # randomized delay according to settings
    params = {'pc': 50, 'v': 'filling'}
    # sleep(uniform(self.delay_range[0], self.delay_range[1]))
    result = requests.get(url, params=params)
    sleep(0.25)
    return BeautifulSoup(result.text, 'lxml')


class Category:
    def __init__(self, stage: int = 0, title: str = None, url: str = None, base_url: str = None, link: str = None,
                 code: int = None, parent_id: int = None, soup: str = None):
        self.base_url = base_url
        self.stage = stage
        self.title = title
        self.url = url
        self.link = link
        self.code = code
        self.parent_id = parent_id
        self.children: dict[str: Category] = {}
        self.soup: str = soup
        #
        if base_url:
            self.add_children()

    def __str__(self):
        return f"{STAGES[self.stage]['indent']}[{self.stage}] {self.title} | id:{self.code} | parent_id:{self.parent_id} | link: {self.link}"

    def print_with_children(self):
        if self.stage != 0:
            logger.info(self)
        for _child in self.children.values():
            _child.print_with_children()

    def get_children_to_csv(self):
        if self.stage != 0:
            yield tuple([self.title, self.code, self.parent_id, self.link])
        for _child in self.children.values():
            _child.get_children_to_csv()

    def titles(self):
        return tuple([self.title, self.code, self.parent_id, self.link])

    def list_of_children(self, list_: list = None):
        if list_ is None:
            list_ = []
        if self.stage != 0:
            list_.append(self.titles())
        for _child in self.children.values():
            _child.list_of_children(list_=list_)
        return list_

    def add_children(self):
        print(self)
        # now we'll look down to the category link in order to create its tree
        # each category consists of 4 elements: top-category, category, brand, sub-category
        # example
        # tovary-i-korma-dlya-sobak - top category
        # tovary-i-korma-dlya-sobak/korm-sukhoy/ - this is a category
        # tovary-i-korma-dlya-sobak/korm-sukhoy/advance_1 - brand
        # tovary-i-korma-dlya-sobak/korm-sukhoy/advance_1/shchenki_1/ - sub-category
        if STAGES[self.stage]['stop']:
            return
        if self.stage in [0, 1] or self.soup is None:
            self.soup = get_page_with_url(self.base_url + self.link)
        catalog = self.soup.find(STAGES[self.stage]['catalog']['tag'], STAGES[self.stage]['catalog']['class'])
        index = 0
        if not catalog:
            return
        for tag in tags(catalog):
            item = tag.find(STAGES[self.stage]['item']['tag'], STAGES[self.stage]['item']['class'])
            # print(item['title'] + ' | ' + item['href'])
            index += 1
            item_code = self.code + index * STAGES[self.stage]['multiplier']
            self.children[item['href']] = Category(stage=self.stage + 1, title=item['title'],
                                                   url=self.base_url + item['href'],
                                                   base_url=self.base_url, link=item['href'], code=item_code,
                                                   parent_id=self.code, soup=tag)
        if self.stage in [0, 1]:
            self.soup.decompose()


if __name__ == "__main__":
    ZOO_URL = 'https://zootovary.ru'
    CATALOG = '/catalog/'
    top = Category(url=ZOO_URL + CATALOG, base_url=ZOO_URL, link=CATALOG, code=0, stage=0)
    # top.print_with_children()
    temp = top.list_of_children()
    print(f'total amount of categories are: {len(temp)}')
    links = [
        "/catalog/tovary-i-korma-dlya-khorkov/aksessuary/",
        "/catalog/tovary-i-korma-dlya-sobak/korm-sukhoy/",
        "/catalog/tovary-i-korma-dlya-khorkov/korm/"
    ]
