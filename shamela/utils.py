def get_number_from_url(url: str) -> int:
    return int(url.split('/')[-1].split('#')[0])
