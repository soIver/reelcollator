from dns_client.adapters.requests import DNSClientSession
from contextlib import closing
from psycopg2 import sql
from urllib.parse import quote
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

    def search(self, name: str):
        request = base_url.replace('!', '/search')
        name = quote(name, encoding='utf-8').replace('25', '')
        request += f"query={name}&include_adult=false&language=ru-RU&page=1"
        return self.session.get(url=request, headers=headers).json()['results'][0]
    
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
        order_by=None, order_dir='DESC'):

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
        params = []

        if genres_included:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_genres WHERE genre_id IN %s)"))
            params.append(tuple(genres_included))
        if genres_excluded:
            conditions.append(sql.SQL("m.id NOT IN (SELECT movie_id FROM movies_genres WHERE genre_id IN %s)"))
            params.append(tuple(genres_excluded))
        if keywords_included:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_keywords WHERE keyword_id IN %s)"))
            params.append(tuple(keywords_included))
        if keywords_excluded:
            conditions.append(sql.SQL("m.id NOT IN (SELECT movie_id FROM movies_keywords WHERE keyword_id IN %s)"))
            params.append(tuple(keywords_excluded))
        if actors:
            conditions.append(sql.SQL("m.id IN (SELECT movie_id FROM movies_actors WHERE actor_id IN %s)"))
            params.append(tuple(actors))
        if director:
            conditions.append(sql.SQL("m.director = %s"))
            params.append(director)
        if title_part:
            conditions.append(sql.SQL("m.name ILIKE %s"))
            params.append(f'%{title_part}%')
        if country:
            conditions.append(sql.SQL("m.release_country = %s"))
            params.append(country)
        if release_date_gte and release_date_lte:
            conditions.append(sql.SQL("m.release_date BETWEEN %s AND %s"))
            params.extend([release_date_gte, release_date_lte])

        if conditions:
            query += sql.SQL(" AND ") + sql.SQL(" AND ").join(conditions)

        query += sql.SQL(" GROUP BY m.id")
        query += sql.SQL(f" ORDER BY {order_by[0] if order_by else 'm.release_date'} {order_dir}")

        rows = self.db_request(query, params=params)

        movies: list[dict] = []
        for row in rows:
            movie = {
                'id': row['id'],
                'name': row['name'],
                'release_date': row['release_date'],
                'release_country': row['release_country'],
                'poster_link': row['poster_link'],
                'rating': round(row['rating'], 1),
                'revenue': row['revenue'],
                'runtime': row['runtime'],
                'director': row['director'],
                'overview': row['overview'],
                'actors': row['actors'],
                'genres': row['genres'],
                'keywords': row['keywords']
            }
            movies.append(movie)
        return movies
    
    def save_movie(self, movie_data: dict):
        query = sql.SQL('''
            UPDATE movies 
            SET name = %s, release_date = %s, release_country = %s, poster_link = %s, 
                rating = %s, revenue = %s, runtime = %s, director = %s, overview = %s
            WHERE id = %s
        ''')
        params = [
            movie_data.get('name'),
            movie_data.get('release_date'),
            movie_data.get('release_country'),
            movie_data.get('poster_link'),
            movie_data.get('rating'),
            movie_data.get('revenue'),
            movie_data.get('runtime'),
            movie_data.get('director'),
            movie_data.get('overview'),
            movie_data.get('id')
        ]
        self.db_request(query, False, params)

        if 'actors_for_delete' in movie_data:
            delete_actors_query = sql.SQL('''
                DELETE FROM movies_actors 
                WHERE movie_id = %s AND actor_id = %s
            ''')
            for actor_id in movie_data.get('actors_for_delete', []):
                if actor_id is None:
                    continue
                self.db_request(delete_actors_query, False, [movie_data.get('id'), actor_id])

        if 'actors_for_insert' in movie_data:
            insert_actors_query = sql.SQL('''
                INSERT INTO movies_actors (movie_id, actor_id)
                VALUES (%s, %s)
            ''')
            for actor_id in movie_data.get('actors_for_insert', []):
                if actor_id is None:
                    continue
                self.db_request(insert_actors_query, False, [movie_data.get('id'), actor_id])

        if 'genres_for_delete' in movie_data:
            delete_genres_query = sql.SQL('''
                DELETE FROM movies_genres 
                WHERE movie_id = %s AND genre_id = %s
            ''')
            for genre_id in movie_data.get('genres_for_delete', []):
                if genre_id is None:
                    continue
                self.db_request(delete_genres_query, False, [movie_data.get('id'), genre_id])

        if 'genres_for_insert' in movie_data:
            insert_genres_query = sql.SQL('''
                INSERT INTO movies_genres (movie_id, genre_id)
                VALUES (%s, %s)
            ''')
            for genre_id in movie_data.get('genres_for_insert', []):
                if genre_id is None:
                    continue
                self.db_request(insert_genres_query, False, [movie_data.get('id'), genre_id])

        if 'keywords_for_delete' in movie_data:
            delete_keywords_query = sql.SQL('''
                DELETE FROM movies_keywords 
                WHERE movie_id = %s AND keyword_id = %s
            ''')
            for keyword_id in movie_data.get('keywords_for_delete', []):
                if keyword_id is None:
                    continue
                self.db_request(delete_keywords_query, False, [movie_data.get('id'), keyword_id])

        if 'keywords_for_insert' in movie_data:
            insert_keywords_query = sql.SQL('''
                INSERT INTO movies_keywords (movie_id, keyword_id)
                VALUES (%s, %s)
            ''')
            for keyword_id in movie_data.get('keywords_for_insert', []):
                if keyword_id is None:
                    continue
                self.db_request(insert_keywords_query, False, [movie_data.get('id'), keyword_id])
        
    def delete_movie(self, movie_id: int):
        query = sql.SQL('DELETE FROM movies WHERE id = %s')
        params = [movie_id]
        self.db_request(query, False, params)
        
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
    
    def get_credits(self, id):
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
        return actors, director

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