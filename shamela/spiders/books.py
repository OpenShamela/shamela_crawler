from collections.abc import Generator
from typing import ClassVar

from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from shamela.utils import get_number_from_url


class Books(CrawlSpider):
    name = 'books'
    allowed_domains: ClassVar[list[str]] = ['shamela.ws']
    start_urls: ClassVar[list[str]] = ['https://shamela.ws/']

    rules = (Rule(LinkExtractor(allow=r'category/'), callback='parse_item', follow=True),)

    def parse_item(self, response: Response) -> Generator[dict[str, str | int], None, None]:
        for book in response.css('.book_item'):
            yield {
                'title': book.css('a.book_title::text').get(),
                'author_id': get_number_from_url(book.css('a.text-gray::attr(href)').get()),
                'category': ' '.join(response.css('h1::text').get().split()[1:]),
                'description': book.css('p.des::text').get().replace('\r', '\n'),
                'pages': int(
                    book.css('p.des::text').re_first(r'عدد الصفحات: ([\u0660-\u0669]+)') or -1
                ),
                'id': get_number_from_url(book.css('a.book_title::attr(href)').get()),
            }
