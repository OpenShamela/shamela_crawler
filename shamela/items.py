# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
from scrapy import Field, Item


class BookItem(Item):
    id = Field()
    title = Field()
    author = Field()
    description = Field()
    category = Field()


class CategoryItem(Item):
    id = Field()
    name = Field()
