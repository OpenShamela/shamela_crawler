# Shamela Crawler

A Python 3 Scrapy web crawler to download data from [Shamela Library](https://shamela.ws/).

## Installation

```bash
# Using poetry
poetry install

# or using pip 18+
pip install .
```

## Usage

### Categories

```bash
scrapy crawl categories -o categories.json
```

### Authors

```bash
scrapy crawl authors -o authors.json
```

### Books list

```bash
scrapy crawl books -o books.json
```

### Single Book

- Book ID is required, it can be found in the URL of the book page on Shamela Library. For example, the book ID
  for [this book](https://shamela.ws/book/1) is `1`.

#### As JSON

```bash
scrapy crawl book -a book_id=1 -s MAKE_JSON=true
```

#### As EPUB

```bash
scrapy crawl book -a book_id=1 -s MAKE_EPUB=true
```

#### Single Book volume as EPUB

```bash
scrapy crawl book -a book_id=1 -a volume_id=1 -s MAKE_EPUB=true
```

#### Single Book with improved Hamesh

```bash
scrapy crawl book -a book_id=1 -s MAKE_EPUB=true -s UPDATE_EPUB_HAMESH=true
```

### Flags

To use any of the following flags, add `-s FLAG_NAME=true` to the command line

- `MAKE_JSON`: Export the book as JSON (default: false). Available for the `book` spider only.
- `MAKE_EPUB`: Export the book as EPUB (default: false). Available for the `book` spider only.
- `UPDATE_EPUB_HAMESH`: Update the EPUB file with the correct Hamesh (default: false)
- `HTTPCACHE_ENABLED` : HTTP cache (default: true). Use `-s HTTPCACHE_ENABLED=False` to disable.
- Any other Scrapy setting can be set using the `-s` flag.
