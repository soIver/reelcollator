from dns_client.adapters.requests import DNSClientSession
from contextlib import closing
from psycopg2 import sql
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
    
    def get_image_bin(self, image_path: str):
        url = image_path
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

    def search_movies(self, 
        genres_included=None, genres_excluded=None, keywords_included=None, 
        keywords_excluded=None, actors=None, director=None, title_part=None, 
        country=None, release_date_gte=None, release_date_lte=None,
        order_by=None, order_dir='ASC'):

        query = sql.SQL("""
        SELECT m.id, m.name, m.release_date, m.release_country, m.poster_link, m.rating, m.revenue, m.runtime, m.director, m.overview,
            array_agg(DISTINCT a.id) AS actors,
            array_agg(DISTINCT g.id) AS genres,
            array_agg(DISTINCT k.id) AS keywords
        FROM movies m
        LEFT JOIN movies_actors ma ON m.id = ma.movie_id
        LEFT JOIN actors a ON ma.actor_id = a.id
        LEFT JOIN movies_genres mg ON m.id = mg.movie_id
        LEFT JOIN genres g ON mg.genre_id = g.id
        LEFT JOIN movies_keywords mk ON m.id = mk.movie_id
        LEFT JOIN keywords k ON mk.keyword_id = k.id
        WHERE 1=1
        """)

        conditions = []
        if genres_included:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_genres WHERE genre_id IN %s)"))
        if genres_excluded:
            conditions.append(sql.SQL("m.id NOT IN (SELECT movie_id FROM movies_genres WHERE genre_id IN %s)"))
        if keywords_included:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_keywords WHERE keyword_id IN %s)"))
        if keywords_excluded:
            conditions.append(sql.SQL("m.id NOT IN (SELECT movie_id FROM movies_keywords WHERE keyword_id IN %s)"))
        if actors:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_actors WHERE actor_id IN %s)"))
        if director:
            conditions.append(sql.SQL("m.director = %s"))
        if title_part:
            conditions.append(sql.SQL("m.name ILIKE %s"))
        if country:
            conditions.append(sql.SQL("m.release_country = %s"))
        if release_date_gte and release_date_lte:
            conditions.append(sql.SQL("m.release_date BETWEEN %s AND %s"))

        if conditions:
            query += sql.SQL(" AND ") + sql.SQL(" AND ").join(conditions)

        query += sql.SQL(" GROUP BY m.id")
        query += sql.SQL(f" ORDER BY {order_by if order_by else 'm.release_date'} {order_dir}")

        # Подготовка параметров для запроса
        params = []
        if genres_included:
            params.append(tuple(genres_included))
        if genres_excluded:
            params.append(tuple(genres_excluded))
        if keywords_included:
            params.append(tuple(keywords_included))
        if keywords_excluded:
            params.append(tuple(keywords_excluded))
        if actors:
            params.append(tuple(actors))
        if director:
            params.append(director)
        if title_part:
            params.append(f'%{title_part}%')
        if country:
            params.append(country)
        if release_date_gte and release_date_lte:
            params.extend([release_date_gte, release_date_lte])

        # Выполнение запроса
        rows = self.db_request(query, params=params)

        # Формирование результата
        movies = []
        for row in rows:
            movie = {
                'id': row['id'],
                'name': row['name'],
                'release_date': row['release_date'],
                'release_country': row['release_country'],
                'poster_link': row['poster_link'],
                'rating': round(row['rating'], 1),
                'revenue': row['revenue'],
                'director': row['director'],
                'overview': row['overview'],
                'actors': row['actors'],
                'genres': row['genres'],
                'keywords': row['keywords']
            }
            movies.append(movie)
        print(movies)
        return movies

    def db_request(self, query: str, get: bool = True, params = None):
        result = None
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                except psycopg2.errors.UniqueViolation:
                    pass
                if get:
                    result = cursor.fetchall()
        return result
    
    def is_cyrillic(self, text):
        pattern = re.compile(r'^[а-яА-ЯёЁ\s-]+$')
        return bool(pattern.match(text))
    
    def get_stats(self) -> dict[str, int]:
        usr_cnt = len(self.db_request(f'SELECT * FROM users'))
        query_month = len(self.db_request(f"SELECT * FROM queries WHERE date > CURRENT_DATE - '1 month':: interval"))
        query_week = len(self.db_request(f"SELECT * FROM queries WHERE date > CURRENT_DATE - '1 week':: interval"))
        query_day = len(self.db_request(f"SELECT * FROM queries WHERE date > CURRENT_DATE - '1 day':: interval"))
        favorite = len(self.db_request(f"SELECT * FROM favorite_movies"))
        watchlist = len(self.db_request(f"SELECT * FROM watchlist"))

        return {'usr_cnt': usr_cnt,
                'query_month': query_month,
                'query_week': query_week,
                'query_day': query_day,
                'favorite': favorite,
                'watchlist': watchlist}

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