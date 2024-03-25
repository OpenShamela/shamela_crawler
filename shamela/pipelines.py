# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# useful for handling different item types with a single interface
import logging

from scrapy import Spider
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from shamela.db import Base, Book, Category


class ShamelaPipeline:
    def open_spider(self, spider: Spider) -> None:
        self.engine = create_engine('sqlite:///shamela.db')
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.book_update_fields = ['title', 'author', 'description']

    def close_spider(self, spider: Spider) -> None:
        self.session.close()
        self.engine.dispose()

    def _handle_book(self, item: dict[str, str]) -> None:
        book = self.session.query(Book).filter_by(id=item['id']).first()
        category = self._handle_category({'name': item['category']})
        category_id = category.id if category else None

        if book:
            for attr in self.book_update_fields:
                if getattr(book, attr) != item[attr]:
                    setattr(book, attr, item[attr])
        else:
            book = Book(
                title=item['title'],
                author=item['author'],
                description=item['description'],
                id=item['id'],
                category_id=category_id,
            )
            self.session.add(book)

        try:
            self.session.commit()
        except SQLAlchemyError as err:
            self.session.rollback()
            logging.error(err)

    def _handle_category(self, category_item: dict[str, str]) -> Category | None:
        if category := self.session.query(Category).filter_by(name=category_item['name']).first():
            return category
        category = Category(name=category_item['name'])
        self.session.add(category)
        try:
            self.session.commit()
        except SQLAlchemyError as err:
            self.session.rollback()
            logging.error(err)
        return category

    def process_item(self, item: dict[str, str], spider: Spider) -> dict[str, str]:
        if spider.name == 'categories':
            self._handle_category(item)
        if spider.name == 'books':
            self._handle_book(item)
        return item
