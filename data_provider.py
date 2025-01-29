from dns_client.adapters.requests import DNSClientSession
from contextlib import closing
import psycopg2, psycopg2.extras, re, requests, xml.etree.ElementTree as ET

base_url = "https://api.themoviedb.org/3!/movie?"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxMjQ3YTcwYmZmYmYzZGZhMWQzNDAxMWEyOWE4ZjdkMyIsInN1YiI6IjY1ZWMwODhlOWQ4OTM5MDE2MjI5OTM4NCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.OxTkKEPFIGD_iIm522Tj18ERii7aE3Su9_Uc996u3yw"
}

dbname='2024_psql_rad'
user='2024_psql_r_usr'
password='g9yyJG0bzVNGW3RH'
host='5.183.188.132'

class DataProvider:
    def __init__(self):
        self.session = DNSClientSession('9.9.9.9')

    def details(self, fid: int) -> dict:
        request = f'{base_url[:-1].replace('!', '')}/{fid}?language=ru-RU'
        return self.session.get(request, headers=headers).json()

    def search(self, params: dict[str, list[str]]):
        request = base_url.replace('!', '/search')
        for key, value in params.items():
            request += f'{key}='
            request += ','.join(value) + '&'
        print(request)
        return self.session.get(url=request.strip('&'), headers=headers).json()['results']
    
    def discover(self, params: dict[str, list[str]]):
        request = base_url.replace('!', '/discover')
        for key, value in params.items():
            request += f'{key}='
            request += ','.join(value) + '&'
        print(request)
        print(self.session.get(url=request.strip('&'), headers=headers).json())
        return self.session.get(url=request.strip('&'), headers=headers).json()['results']
         
    def api_request(self, search_params: dict[str, list[str]] = None, discover_params: dict[str, list[str]] = None):
        discover_response: list[dict] = []
        search_response: list[dict] = []
        if search_params:
            search_response = self.search(search_params)
        if discover_params:
            discover_response = self.discover(discover_params)
        if discover_response and search_response:
            response = [film for film in discover_response if film in search_response]
        elif discover_response: 
            response = discover_response
        elif search_response: 
            response = search_response
        else: 
            response = False
        return response
    
    def get_image_bin(self, image_path: str):
        url = f'https://image.tmdb.org/t/p/original{image_path}'
        response = self.session.get(url, stream=True, timeout=20)
        return response.content
            
    def get_countries(self):
        url = "https://www.artlebedev.ru/country-list/xml/"
        response = requests.get(url)
        root = ET.fromstring(response.content)
        countries = {}
        for country in root.findall('country'):
            country_name = country.find('name').text
            country_id = country.find('alpha2').text
            if country_name:
                countries[country_id] = country_name
        return countries

    def db_request(self, query: str, get: bool = True):
        result = None
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    cursor.execute(query)
                except psycopg2.errors.UniqueViolation:
                    pass
                if get:
                    result = cursor.fetchall()
        return result
    
    def is_cyrillic(self, text):
        pattern = re.compile(r'^[а-яА-ЯёЁ\s-]+$')
        return bool(pattern.match(text))
    
    def get_data(self, countries):
        burl = "https://api.themoviedb.org/3/trending/movie/week?language=ru-RU&page="
        for i in range(2, 5, 1):
            url = burl + str(i+1)
            response = self.session.get(url, headers=headers).json()['results']
            print(url)
            for movie in response:
                id = movie['id']
                title = movie['title']
                overview = movie['overview']
                poster_path = f'https://image.tmdb.org/t/p/original{movie['poster_path']}'
                genres = movie['genre_ids']
                release_date = movie['release_date']
                rating = movie['vote_average']
                details = self.details(id)
                revenue = details['revenue']
                runtime = details['runtime']
                country_id = details['origin_country'][0]
                actors = []
                director = None
                credits_url = f"https://api.themoviedb.org/3/movie/{id}/credits?language=ru-RU"
                credits_response = self.session.get(credits_url, headers=headers).json()
                cast: list = credits_response['cast']
                crew = credits_response['crew']
                credits_response = cast + crew
                for credit in credits_response:
                    name = credit['name']
                    if self.is_cyrillic(name):
                        ns = name.split()
                        if len(ns) < 2:
                            continue
                        if credit['known_for_department'] == 'Acting':
                            actors.append((credit['id'], ns[0], ns[1]))
                        elif credit['known_for_department'] == 'Directing':
                            director = [credit['id'], ns[0], ns[1]]
                            break
                if director:
                    print(id, title, overview, poster_path, genres, release_date, rating, revenue, runtime, country_id, actors, director)
                    self.db_request(f"INSERT INTO directors VALUES ({director[0]}, '{director[1]}', '{director[2]}')", False)
                    self.db_request(f"INSERT INTO movies VALUES ({id}, '{title}', '{release_date}', '{countries[country_id]}', '{poster_path}', {rating}, {revenue}, {director[0]}, '{overview}')", False)
                    for actor in actors:
                        self.db_request(f"INSERT INTO actors VALUES ({actor[0]}, '{actor[1]}', '{actor[2]}')", False)
                        self.db_request(f"INSERT INTO movies_actors VALUES ({id}, {actor[0]})", False)