from collections.abc import Generator
from typing import ClassVar

from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule


class Authors(CrawlSpider):
    name = 'authors'
    allowed_domains: ClassVar[list[str]] = ['shamela.ws']
    start_urls: ClassVar[list[str]] = ['https://shamela.ws/authors']

    rules = (Rule(LinkExtractor(allow=r'author/'), callback='parse_item', follow=False),)

    def parse_item(self, response: Response) -> Generator[dict[str, str | int], None, None]:
        yield {
            'id': int(response.url.split('/')[-1]),
            'name': response.css('h1::text').get(),
            'bio': '\n'.join(response.css('.heading-title + .alert::text').getall()),
        }
