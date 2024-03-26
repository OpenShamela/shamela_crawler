# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# useful for handling different item types with a single interface
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from scrapy import Spider
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from shamela.db import Author, Base, Book, Category

F = TypeVar('F', bound=Callable[..., Any])

commit_threshold = 100


def commit_session(func: F) -> F:
    counter = 0

    @wraps(func)
    def wrapped_func(self: 'ShamelaPipeline', session: Session, *args: Any, **kwargs: Any) -> Any:
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


class ShamelaPipeline:
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
