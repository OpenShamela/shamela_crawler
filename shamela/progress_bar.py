from scrapy import Item, Request, Spider, signals
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.statscollectors import StatsCollector
from tqdm import tqdm


class ProgressBarExtension:
    def __init__(self, stats: StatsCollector) -> None:
        self.stats = stats
        self.items_scraped = 0
        self.items_dropped = 0
        self.pages_crawled = 0
        self.progress_bar = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'ProgressBarExtension':
        ext = cls(crawler.stats)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(ext.page_crawled, signal=signals.response_received)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def item_scraped(self, item: Item, response: Response, spider: Spider) -> None:
        self.items_scraped += 1
        self.update_progress_bar()

    def item_dropped(
        self, item: Item, response: Response, exception: Exception, spider: Spider
    ) -> None:
        self.items_dropped += 1
        self.update_progress_bar()

    def page_crawled(self, response: Response, request: Request, spider: Spider) -> None:
        if self.progress_bar is None:
            self.progress_bar = tqdm(total=self.stats.get_value('downloader/response_count'))
        self.pages_crawled += 1
        # Update the total number of pages in the progress bar after the first page is crawled in book spider
        if (
            self.progress_bar
            and self.progress_bar.total == 1
            and spider.name == 'book'
            and 'data' in response.meta
            and int(response.url.split('/')[-1]) > 1
        ):
            self.progress_bar.total = response.meta['data']['info']['all_pages']
        self.update_progress_bar()

    def update_progress_bar(self) -> None:
        if self.progress_bar is not None:
            self.progress_bar.set_description(
                f'Pages: {self.pages_crawled} Items: {self.items_scraped} Dropped: {self.items_dropped}'
            )
            self.progress_bar.update()

    def spider_closed(self, spider: Spider, reason: str) -> None:
        if self.progress_bar is not None:
            self.progress_bar.close()
