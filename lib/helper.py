from bs4 import Tag


def tags(items) -> Tag:
    for item in items:
        if not isinstance(item, Tag):
            continue
        yield item
