from collections.abc import Generator
from typing import Any, ClassVar

from scrapy import Spider
from scrapy.http import Response


class CategoriesSpider(Spider):
    name = 'categories'
    allowed_domains: ClassVar[list[str]] = ['shamela.ws']
    start_urls: ClassVar[list[str]] = ['https://shamela.ws/']

    def parse(self, response: Response, **kwargs: Any) -> Generator[dict[str, str], None, None]:
        for category in response.css('.cat_title'):
            yield {
                'id': category.css('::attr(href)').get().split('/')[-1],
                'name': ' '.join(category.css('::text').get().split()[1:]),
            }
