# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# useful for handling different item types with a single interface
import logging
from collections.abc import Callable
from functools import wraps
from io import BufferedWriter
from pathlib import Path
from typing import Any, TypeVar, cast

from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.exporters import BaseItemExporter
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from shamela.db import Author, Base, Book, Category
from shamela.exporters.epub import EpubItemExporter
from shamela.exporters.json import SortedJsonItemExporter

F = TypeVar('F', bound=Callable[..., Any])

commit_threshold = 100


def commit_session(func: F) -> F:
    counter = 0

    @wraps(func)
    def wrapped_func(self: 'DatabasePipeline', session: Session, *args: Any, **kwargs: Any) -> Any:
        nonlocal counter
        result = func(self, session, *args, **kwargs)
        counter += 1
        if counter >= commit_threshold:
            try:
                session.commit()
            except SQLAlchemyError as err:
                session.rollback()
                logging.error(err)
            finally:
                counter = 0
        return result

    return cast(F, wrapped_func)


class DatabasePipeline:
    def open_spider(self, spider: Spider) -> None:
        self.engine = create_engine('sqlite:///shamela.db')
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.book_update_fields = ['title', 'author_id', 'description']
        self.author_update_fields = ['name', 'bio']

    def close_spider(self, spider: Spider) -> None:
        self.session.commit()
        self.session.close()
        self.engine.dispose()

    @commit_session
    def _handle_book(self, session: Session, item: dict[str, str]) -> None:
        book = session.query(Book).filter_by(id=item['id']).first()
        if book:
            for attr in self.book_update_fields:
                if getattr(book, attr) != item[attr]:
                    setattr(book, attr, item[attr])
        else:
            author = self.session.query(Author).filter_by(id=item['author_id']).first()
            book = Book(
                title=item['title'],
                description=item['description'],
                id=item['id'],
                category_id=self._handle_category(session, {'name': item['category']}).id,
                author_id=author.id if author else None,
            )
            session.add(book)

    @commit_session
    def _handle_category(self, session: Session, category_item: dict[str, str]) -> Category:
        category = session.query(Category).filter_by(name=category_item['name']).first()
        if not category:
            category = Category(name=category_item['name'])
            session.add(category)
        return category

    @commit_session
    def _handle_author(self, session: Session, author_item: dict[str, str]) -> Author | None:
        author = session.query(Author).filter_by(id=author_item['id']).first()
        if author:
            for attr in self.author_update_fields:
                if getattr(author, attr) != author_item[attr]:
                    setattr(author, attr, author_item[attr])
        else:
            author = Author(**author_item)
            session.add(author)
        return author

    def process_item(self, item: dict[str, str], spider: Spider) -> dict[str, str]:
        if spider.name == 'categories':
            self._handle_category(self.session, item)
        if spider.name == 'authors':
            self._handle_author(self.session, item)
        if spider.name == 'books':
            self._handle_book(self.session, item)
        return item


class BookJSONExportPipeline:
    def __init__(self) -> None:
        self.exporter: BaseItemExporter | None = None
        self.file: BufferedWriter | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'BookJSONExportPipeline':
        if not crawler.settings.getbool('MAKE_JSON'):
            raise NotConfigured
        return cls()

    def close_spider(self, spider: Spider) -> None:
        if self.exporter:
            self.exporter.finish_exporting()
        if self.file:
            self.file.close()

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        if spider.name != 'book' or 'info' not in item or self.file:
            return item

        file = Path(f"{item['info']['title']}.json")
        if file.exists():
            file.unlink(missing_ok=True)
        self.file = file.open('wb')
        self.exporter = SortedJsonItemExporter(self.file)
        self.exporter.export_item(item)
        return item


class BookEPUBExportPipeline:
    def __init__(self) -> None:
        self.exporter: BaseItemExporter | None = None
        self.file: BufferedWriter | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'BookEPUBExportPipeline':
        if not crawler.settings.getbool('MAKE_EPUB'):
            raise NotConfigured
        return cls()

    def close_spider(self, spider: Spider) -> None:
        if self.exporter:
            self.exporter.finish_exporting()
        if self.file:
            self.file.close()

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        if spider.name != 'book' or 'info' not in item or 'pages' not in item or self.file:
            return item

        file = Path(
            f"{item['info']['title']} - {item['info']['author']} - ({item['info']['id']}).epub"
        )
        if file.exists():
            file.unlink(missing_ok=True)
        self.file = file.open('wb')
        self.exporter = EpubItemExporter(self.file)
        self.exporter.start_exporting()
        self.exporter.export_item(item)
        return item
