import re
from collections.abc import Generator
from enum import Enum
from re import Pattern
from typing import Any, ClassVar

from scrapy import Request, Selector
from scrapy.http import Response
from scrapy.selector import SelectorList
from scrapy.spiders import Spider

TocType = list[dict[str, Any] | list[dict[str, Any]]]


class Selectors(Enum):
    PAGE_CONTENT = '.nass'
    SEARCH = 'div.text-left'
    INDEX = 'div.betaka-index'
    TOC = 'h4 + ul > li'
    CHAPTERS = "ul a[href*='/book/']"
    AUTHOR = 'h1 + div a::text'
    TITLE = 'h1 a::text'
    COPY_BTN = 'a.btn_tag'
    PAGE_NUMBER = 'input#fld_goto_bottom'
    PAGE_PARTS = '#fld_part_top ~ div'
    PAGE_PARTS_MENU = f"{PAGE_PARTS} ul[role='menu']"
    PAGE_PART = f'{PAGE_PARTS} button::text'
    NEXT_PAGE = f'{PAGE_NUMBER} + a'
    LAST_PAGE = f'{PAGE_NUMBER} + a + a'


class Book(Spider):
    name = 'book'
    allowed_domains: ClassVar[list[str]] = ['shamela.ws']

    PARENT_DIV_CLASS_PATTERN: Pattern = re.compile(r' class="nass margin-top-10"')
    HTML_STYLE_PATTERN: Pattern = re.compile(r' style="(.*?)"')

    def __init__(self, book_id: int, vol: str = '', *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.book_id = book_id
        self.start_urls = [f'https://shamela.ws/book/{book_id}']
        self.vol = vol

    def parse(
        self, response: Response, **kwargs: Any
    ) -> Generator[dict[str, str | int], None, None]:
        html = response.css(Selectors.PAGE_CONTENT.value)
        html.css(Selectors.SEARCH.value).drop()  # Remove "Search" button
        toc_el = html.css(Selectors.INDEX.value)
        toc_ul: SelectorList = toc_el.css(Selectors.TOC.value)
        toc_ul.css('a[href="javascript:;"]').drop()
        toc = self._parse_toc(toc_ul)
        page_chapters = self._chapters_by_page(html.css(Selectors.CHAPTERS.value))
        toc_el.drop()  # Remove the "Index" section
        data = {
            'info': {
                'title': response.css(Selectors.TITLE.value).get(),
                'author': response.css(Selectors.AUTHOR.value).get(),
                'about': self.PARENT_DIV_CLASS_PATTERN.sub('', html.get()),
                'toc': toc,
                'page_chapters': page_chapters,
            }
        }
        book_text_url = f'https://shamela.ws/book/{self.book_id}/1'
        yield response.follow(book_text_url, self.parse_book_text, meta={'data': data})

    def parse_book_text(  # noqa: C901, PLR0912
        self, response: Response, **kwargs: Any
    ) -> Generator[dict[str, str | int], None, None]:
        """
        Parse the book text pages
        :param response:
        :param kwargs:
        :return:
        """
        page_number = int(response.url.split('/')[-1])
        page = int(response.css(f'{Selectors.PAGE_NUMBER.value}::attr(value)').get('0'))
        data = response.meta['data']
        if 'text' not in data:
            data['text'] = []

        if page_number == 1:
            data['info']['all_pages'] = int(
                response.css(f'{Selectors.LAST_PAGE.value}::attr(href)').re_first(r'(\d+)#')
            )
            data['info']['volumes'] = {}
            if parts := response.css(Selectors.PAGE_PARTS_MENU.value):
                volumes = {}
                for part in parts.css('li a')[1:]:
                    volumes[part.css('::text').get()] = int(
                        part.css('::attr(href)').re_first(r'(\d+)#')
                    )
                data['info']['volumes'] = self._get_start_end_pages(volumes)
            # Check if the required volume is valid
            if self.vol and not response.css(f'{Selectors.PAGE_PARTS_MENU.value} li a::text')[
                1:
            ].re(self.vol):
                raise ValueError(f'Volume {self.vol} not found in book {self.book_id}')
            # if current page is not the required volume, jump to required volume's first page
            if self.vol and self.vol != response.css(Selectors.PAGE_PART.value).get().strip():
                yield Request(
                    url=f"https://shamela.ws/book/{self.book_id}/{data['info']['volumes'][self.vol][0]}",
                    callback=self.parse_book_text,
                    meta={'data': data},
                )
                return
        # Check if the current page is the last page of the volume
        if self.vol and page_number > data['info']['volumes'][self.vol][1]:
            data = self._update_data_for_one_volume(data, data['info']['volumes'][self.vol])
            data['info']['pages'] = len(data['text'])
            yield data
            return

        html = response.css(Selectors.PAGE_CONTENT.value)
        html.css(Selectors.COPY_BTN.value).drop()  # Remove "Copy" button
        html = Selector(text=self.PARENT_DIV_CLASS_PATTERN.sub('', html.get()))
        # Delete empty spans
        for element in html.css('span'):
            if not element.css('::text').get():
                element.drop()
        # Delete paragraph style
        for _ in html.css('p[style="font-size: 15px"]'):
            _ = Selector(text=self.HTML_STYLE_PATTERN.sub('', html.get()))

        data['text'].append(
            {
                'page_number': page_number,
                'page': page,
                'text': html.get(),
                # 'html': response.css('.padding-top-20 .container').get()
            }
        )

        # Follow pagination links and parse those pages
        if not response.css(Selectors.LAST_PAGE.value):
            if self.vol and page_number == data['info']['volumes'][self.vol][1]:
                data = self._update_data_for_one_volume(data, data['info']['volumes'][self.vol])
            data['info']['pages'] = len(data['text'])
            yield data
        else:
            yield response.follow(
                response.css(Selectors.NEXT_PAGE.value).attrib.get('href'),
                self.parse_book_text,
                meta={'data': data},
            )

    def _parse_toc(self, toc: SelectorList) -> TocType:
        """
        Parse the table of contents into a list of dictionaries
        :param toc: table of contents
        :return: list of dictionaries
        """
        toc_list: list = []
        item: Selector
        for item in toc:
            link = {
                'page': int(item.css('a::attr(href)').get().split('/')[-1]),
                'text': item.css('a::text').get(''),
            }
            ul_list: SelectorList = item.css('li ul')
            if ul_list:
                toc_list.append([link, self._parse_toc(ul_list.css('ul li'))])
            else:
                toc_list.append(link)
        return toc_list

    @staticmethod
    def _chapters_by_page(chapters_list: SelectorList) -> dict[str, Any]:
        """
        Build a dictionary of chapters by page number
        :param chapters_list: list of chapters
        :return: dict of chapters by page number
        """
        chapters: dict = {}
        for chapter in chapters_list:
            chapter_page = int(chapter.css('::attr(href)').get().split('/')[-1])
            if chapter_page not in chapters:
                chapters[chapter_page] = []
            chapters[chapter_page].append(chapter.css('::text').get('').strip())
        return chapters

    def _cut_toc(
        self, toc: list[dict[str, Any]], start_end: tuple[int, int]
    ) -> list[dict[str, Any]]:
        """
        Cut the table of contents to the required volume
        :param toc: list of table of contents
        :param start_end: tuple of start and end pages
        :return: list of table of contents
        """
        result = []
        for item in toc:
            if isinstance(item, list):
                sub_toc = self._cut_toc(item, start_end)
                if sub_toc:
                    result.append(sub_toc)
            elif start_end[1] >= item['page'] >= start_end[0]:
                result.append(item)
            else:
                break
        return result

    def _update_data_for_one_volume(
        self, data: dict[str, Any], start_end: tuple[int, int]
    ) -> dict[str, Any]:
        """
        Cut the table of contents to the required volume
        :param data:
        :param start_end:
        :return:
        """
        data['info']['page_chapters'] = {
            k: v
            for k, v in data['info']['page_chapters'].items()
            if start_end[1] >= k >= start_end[0]
        }
        data['info']['toc'] = self._cut_toc(data['info']['toc'], start_end)
        data['info']['volumes'] = {self.vol: start_end}
        data['info']['title'] = f"{data['info']['title']} - {self.vol}"
        return data

    @staticmethod
    def _get_start_end_pages(volumes: dict[str, int]) -> dict[str, tuple[int, int]]:
        """
        Get start and end pages for each volume
        :param volumes: dict of volumes and their last page number
        :return: dict of volumes and their start and end pages
        """
        start_end_pages = {}
        prev_volume_name = None

        for volume_name in volumes:
            start_page = 1 if not prev_volume_name else volumes[prev_volume_name] + 1  # type: ignore[index]
            end_page = volumes[volume_name]
            start_end_pages[volume_name] = (start_page, end_page)
            prev_volume_name = volume_name

        return start_end_pages
