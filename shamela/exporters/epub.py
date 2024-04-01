import re
from copy import deepcopy
from io import BytesIO
from re import Pattern
from typing import Any, BinaryIO

from ebooklib import epub
from lxml.etree import Element, QName, tostring
from scrapy.exporters import BaseItemExporter
from scrapy.selector import Selector, SelectorList

CSS_STYLE_COLOR_PATTERN: Pattern = re.compile(r'style="(color:#[\w\d]{6})"')
HAMESH_CONTINUATION_PATTERN: Pattern = re.compile(r'(?<=>)(?P<continuation>=.+?)(?=<br>|</p>)')
HAMESH_PATTERN: Pattern = re.compile(
    r'(?P<number>\([\u0660-\u0669]+\))(?P<content>.+?)(?:</?br/?>(?=\([\u0660-\u0669]+\))|</p>)'
)
ARABIC_NUMBER_BETWEEN_BRACKETS_PATTERN: Pattern = re.compile(r'(?P<number>\([\u0660-\u0669]+\))')
ARABIC_NUMBER_BETWEEN_CURLY_BRACES_PATTERN: Pattern = re.compile(r'{.+?(\([\u0660-\u0669]+\)).+?}')
SPECIAL_CHARACTERS = {
    '﵀': 'رحمه الله',
    '﵏': 'رحمهم الله',
    '﷿': 'عز وجل',
    '﵊': 'عليه الصلاة والسلام',
    '﵄': 'رضي الله عنهما',
    '﵃': 'رضي الله عنهم',
    '﵅': 'رضي الله عنهن',
    '﵂': 'رضي الله عنها',
    '﵁': 'رضي الله عنه',
    '﷾': 'سبحانه وتعالى',
    '﵎': 'تبارك وتعالى',
    '﵇': 'عليه السلام',
    '﵍': 'عليها السلام',
    '﵈': 'عليهم السلام',
    '﵉': 'عليهما السلام',
    '﵌': 'صلى الله عليه وآله وسلم',
}
SPECIAL_CHARACTERS_PATTERN = re.compile('|'.join(map(re.escape, SPECIAL_CHARACTERS.keys())))
TITLE_PATTERN = re.compile(r'<p><span class="([^"]*)">\[[^\]]*\]</span></p>')
EPUB_CSS = (
    '*{direction: rtl}.text-center, h2{text-align: center}.hamesh{font-size: smaller}'
    '.fn{font-size: x-small;vertical-align: super;color: inherit}.nu{text-decoration: none}'
    '.hamesh .nu{color: #008000}'
)
EPUB_TYPE = QName('http://www.idpf.org/2007/ops', 'type')


class EpubItemExporter(BaseItemExporter):
    def __init__(self, file: BytesIO | BinaryIO, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.file = file
        self.book = epub.EpubBook()
        self._pages_count: int = 0
        self._zfill_length = 0
        self._pages: list[epub.EpubHtml] = []
        self._sections: list[epub.Link] = []
        self._sections_map: dict[str, epub.Link] = {}
        self._toc: list[str] = []
        self._default_css: epub.EpubItem = epub.EpubItem()
        self._color_styles_map: dict[str, int] = {}
        self._last_color_id: int = 0
        self._previous_page_hamesh = ''

    def replace_color_styles_with_class(self, html_str: str) -> str:
        matches = CSS_STYLE_COLOR_PATTERN.findall(html_str)
        if not matches:
            return html_str
        for style in list(set(CSS_STYLE_COLOR_PATTERN.findall(html_str))):
            color_class = self._color_styles_map.get(style, '')
            if not color_class:
                color_class = f'color-{self._last_color_id + 1}'
                self._color_styles_map.update({style: color_class})
                self._last_color_id += 1
                self._default_css.content += f'\n.{color_class} {{ {style}; }}\n\n'
            html_str = re.sub(f'style="{style}"', f'class="{color_class}"', html_str)
        return html_str

    def _get_hamesh_items(self, content: Selector) -> dict[str, Element]:
        hamesh_items: dict[str, Element] = {}
        hamesh: SelectorList = content.css('.hamesh')
        if not hamesh:
            return hamesh_items
        hamesh_counter = 0
        hamesh_continuation = HAMESH_CONTINUATION_PATTERN.search(str(hamesh))
        if hamesh_continuation:
            self._previous_page_hamesh = (
                hamesh_continuation.group('continuation')
                if not self._previous_page_hamesh
                else f"{self._previous_page_hamesh}\n{hamesh_continuation.group('continuation')}"
            )
        elif not self._previous_page_hamesh:
            self._previous_page_hamesh = ''
        for match in HAMESH_PATTERN.finditer(hamesh.get('')):
            hamesh_counter += 1
            current_hamesh = match.group('number').strip()
            hamesh_line = match.group('content').strip()
            #  <aside id="fn1" epub:type="footnote">
            #  <p><a href="#fnref1" title="footnote 1">[1]</a> Text in popup</p>
            #  </aside>
            new_footnote_aside = Element(
                'aside',
                {'id': f'fn{hamesh_counter}', EPUB_TYPE: 'footnote'},
            )
            new_footnote_span = Element('span')
            new_footnote_a = Element(
                'a',
                {
                    'href': f'#fnref{hamesh_counter}',
                    # "title": f"هامش {hamesh_counter}",
                    'class': 'nu',
                },
            )
            new_footnote_a.text = current_hamesh
            if self._previous_page_hamesh:
                new_footnote_span.text = self._previous_page_hamesh.replace('\n', '<br>')
                new_footnote_span.append(Element('br'))
                new_footnote_span.text = ' ' + hamesh_line.strip()
                self._previous_page_hamesh = ''
            else:
                new_footnote_span.text = ' ' + hamesh_line.strip()
            new_footnote_aside.append(new_footnote_a)
            new_footnote_aside.append(new_footnote_span)
            hamesh_items.update({current_hamesh: new_footnote_aside})
        return hamesh_items

    def _update_hamesh(self, content: Selector, hamesh_items: dict[str, Element]) -> Selector:
        footnote_count = 1
        hamesh: SelectorList = content.css('.hamesh')
        if not hamesh:
            return content
        new_hamesh: Element = Element('div', {'class': 'hamesh'})
        parent: SelectorList = content.css('div')
        p_elements: SelectorList = content.css('p:not(.hamesh)')
        for p in p_elements:
            matches = ARABIC_NUMBER_BETWEEN_BRACKETS_PATTERN.finditer(p.get())
            for match in matches:
                number = match.group('number')
                if hamesh_items.get(number) is None:
                    continue
                aya_match = ARABIC_NUMBER_BETWEEN_CURLY_BRACES_PATTERN.search(p.get())
                if (
                    aya_match
                    and number in aya_match.group()
                    # number in inside aya
                    and match.start('number') > aya_match.start()
                ):
                    continue
                footnote_link: Element = Element(
                    'a',
                    {
                        'href': f'#fn{footnote_count}',
                        EPUB_TYPE: 'noteref',
                        'role': 'doc-noteref',
                        'id': f'fnref{footnote_count}',
                        # "title": f"هامش {footnote_count}",
                        'class': 'fn nu',
                    },
                )
                footnote_link.text = number
                # new_p_content = (
                #     str(p)[len("<p>") : match.start()]
                #     + str(footnote_link)
                #     + str(p)[match.start() + len(match.group()) : 0 - len("</p>")]
                # )
                # TODO: Find a better way to replace number with its a element,
                #  since replacing only the first occurrence might not be the best solution
                new_p_el = p.get().replace(number, self.element_as_text(footnote_link), 1)
                content = Selector(text=parent.get('').replace(p.get(), new_p_el))
                footnote_count += 1
                new_hamesh.append(hamesh_items[number])
        return Selector(
            text=content.get().replace(hamesh.get(''), self.element_as_text(new_hamesh))
        )

    @staticmethod
    def element_as_text(element: Element) -> str:
        element_text: str = tostring(element, encoding='utf-8').decode()
        assert isinstance(element_text, str)
        return element_text

    def create_toc_depth_map(
        self, toc: list[dict[str, Any]], depth_map: dict[str, int] | None = None, depth: int = 1
    ) -> dict[str, int]:
        if depth_map is None:
            depth_map = {}
        for item in toc:
            if isinstance(item, list):
                self.create_toc_depth_map(item, depth_map, depth + 1)
            else:
                depth_map[item['text']] = max(2, min(depth, 6))
        return depth_map

    @staticmethod
    def replace_titles_with_headers(
        chapters_in_page: dict[str, list[str]], text: str, toc_depth_map: dict[str, int]
    ) -> str:
        for title in chapters_in_page:
            if f'[{title}]' not in text:
                continue
            if match := TITLE_PATTERN.search(text):
                color_class = match.group(1)
                depth = max(2, min(toc_depth_map.get(title, 2), 6))
                text = text.replace(
                    f'<p><span class="{color_class}">[{title}]</span></p>',
                    f'<h{depth} class="{color_class}">{title}</h{depth}>',
                )
        return text

    def add_chapter(self, chapters_in_page: dict[str, list[str]], page_filename: str) -> None:
        for i in chapters_in_page:
            link = epub.Link(
                page_filename,
                i,
                page_filename.replace('.xhtml', ''),
            )
            self._sections.append(link)
            self._sections_map.update({i: link})

    def _update_toc_list(self, toc: list) -> None:
        # Bug: Books that have a last nested section with level deeper than its next with the same page number
        # cannot be converted to KFX unless that last nested section is removed, or flattened.
        for index, element in enumerate(toc):
            if isinstance(element, list):
                self._update_toc_list(element)
            else:
                toc[index] = self._sections_map.get(element['text'], None)

    def generate_toc(self, toc: list) -> None:
        toc_list: list[epub.Link | str] = deepcopy(toc)
        self._update_toc_list(toc_list)
        toc_list.insert(0, epub.Link('nav.xhtml', 'فهرس الموضوعات', 'nav'))
        toc_list.insert(0, epub.Link('info.xhtml', 'بطاقة الكتاب', 'info'))
        self.book.toc = toc_list
        self.book.add_item(epub.EpubNcx())
        nav = epub.EpubNav()
        nav.add_item(self._default_css)
        self.book.add_item(nav)
        self.book.spine = [
            self._pages[0],
            'nav',
            *self._pages[1:],
        ]  # [info, nav, rest]

    def start_exporting(self) -> None:
        self.book.set_language('ar')
        self.book.set_direction('rtl')
        self.book.add_metadata('DC', 'publisher', 'https://shamela.ws')
        self.book.add_metadata(None, 'meta', '', {'name': 'shamela_crawler', 'content': 'beta'})
        self._default_css = epub.EpubItem(
            uid='style_default',
            file_name='style/styles.css',
            media_type='text/css',
            content=EPUB_CSS,
        )
        self.book.add_item(self._default_css)

    def export_item(self, item: dict[str, Any]) -> dict[str, Any]:
        info, pages = item.values()
        # set pages count from last page number
        self._zfill_length = len(str(pages[-1]['page_number'])) + 1
        # info page
        self.book.set_title(info['title'])
        self.book.add_author(info['author'])
        self.book.add_metadata('DC', 'source', info['url'])
        info_page = epub.EpubHtml(
            title='بطاقة الكتاب',
            file_name='info.xhtml',
            lang='ar',
            content=f"<html><body>{info['about']}</body></html>",
        )
        info_page.add_item(self._default_css)
        self.book.add_item(info_page)
        self._pages.append(info_page)
        toc_depth_map = self.create_toc_depth_map(info['toc'])
        # pages
        for page in pages:
            page_title = ''
            if chapters_in_page := info['page_chapters'].get(page['page_number']):
                page_title = chapters_in_page[0]
            # get page volume
            page_volume_idx, page_volume = next(
                (
                    (index, k)
                    for index, (k, v) in enumerate(info['volumes'].items())
                    if v[0] <= page['page'] <= v[1]
                ),
                (1, ''),
            )
            page_filename = (
                f"page{'_' if page_volume else ''}{page_volume_idx}_"
                f"{str(page['page_number']).zfill(self._zfill_length)}.xhtml"
            )
            footer = ''
            if page_volume:
                footer += f'الجزء: {page_volume} - '
            footer += f"الصفحة: {page['page']}"
            text = self.replace_color_styles_with_class(page['text'])
            text = SPECIAL_CHARACTERS_PATTERN.sub(
                lambda match: SPECIAL_CHARACTERS[match.group(0)], text
            )
            if chapters_in_page:
                text = self.replace_titles_with_headers(chapters_in_page, text, toc_depth_map)
                self.add_chapter(chapters_in_page, page_filename)
            content = Selector(text=text)
            text = self._update_hamesh(content, self._get_hamesh_items(content)).css('div').get('')
            new_page = epub.EpubHtml(
                title=page_title,
                file_name=page_filename,
                lang='ar',
                content=f'<html><body>{text}<div class="text-center">{footer}</div></body></html>',
            )
            new_page.add_item(self._default_css)
            self.book.add_item(new_page)
            self._pages.append(new_page)
        self.generate_toc(info['toc'])
        return item

    def finish_exporting(self) -> None:
        epub.write_epub(self.file, self.book)
