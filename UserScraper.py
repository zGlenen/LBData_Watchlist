import requests
from bs4 import BeautifulSoup

class UserScraper:
    def __init__(self, base_url="https://letterboxd.com/"):
        self.base_url = base_url

    def scrape_user(self, username, type):
        films = []
        url = f"{self.base_url}{username}/{type}/"
        page = requests.get(url)        
        if not page.ok:
            return False
        soup = BeautifulSoup(page.content, "html.parser")
        last_page_element = soup.select_one('.paginate-pages ul li.paginate-page:last-child a')
        last_page_number = int(last_page_element.text) if last_page_element else 1

        for page_number in range(1, last_page_number + 1):
            url_addon = f"page/{page_number}" if page_number > 1 else ""
            page_url = f"{url}{url_addon}"
            page = requests.get(page_url)
            soup = BeautifulSoup(page.content, "html.parser")
            films.extend([div.get('data-film-slug') for div in soup.select("li.poster-container div.really-lazy-load")])

        return films

    def get_uris(self, films):

        x = []
        for slug in films:
            slug = f"{self.base_url}film/{slug}/"
            x.append((slug))
        return x
