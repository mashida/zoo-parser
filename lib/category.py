from random import uniform
from time import sleep

import requests
from bs4 import BeautifulSoup

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
            print(self)
        for _child in self.children.values():
            _child.print_with_children()

    def add_children(self):
        if STAGES[self.stage]['stop']:
            return
        if self.stage in [0, 1]:
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

    def get_by_link(self, link: str = None, stage: int = 0):
        parts = link[1:-1].split('/')
        # print(f'{len(parts)} : {parts}')
        if link in self.children.keys():
            return self.children[link]
        else:
            partial_link = f'/{"/".join(parts[0:stage+1])}/'
            return self.children[partial_link].get_by_link(link, stage + 1)


if __name__ == "__main__":
    ZOO_URL = 'https://zootovary.ru'
    CATALOG = '/catalog/'
    top = Category(url=ZOO_URL + CATALOG, base_url=ZOO_URL, link=CATALOG, code=0, stage=0)
    top.print_with_children()
    category = top.get_by_link('/catalog/tovary-i-korma-dlya-reptiliy/', 1)
    print('*' * 30)
    category.print_with_children()
