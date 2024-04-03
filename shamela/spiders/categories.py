from collections.abc import Generator
from typing import Any, ClassVar

from scrapy import Spider
from scrapy.http import Response

from shamela.utils import get_number_from_url


class CategoriesSpider(Spider):
    name = 'categories'
    allowed_domains: ClassVar[list[str]] = ['shamela.ws']
    start_urls: ClassVar[list[str]] = ['https://shamela.ws/']

    def parse(
        self, response: Response, **kwargs: Any
    ) -> Generator[dict[str, str | int], None, None]:
        for category in response.css('.cat_title'):
            yield {
                'id': get_number_from_url(category.css('::attr(href)').get()),
                'name': ' '.join(category.css('::text').get().split()[1:]),
            }
