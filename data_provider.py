from dns_client.adapters.requests import DNSClientSession
from contextlib import closing
from psycopg2 import sql
from urllib.parse import quote
import psycopg2, psycopg2.extras, re, requests, xml.etree.ElementTree as ET
from decouple import config

base_url = "https://api.themoviedb.org/3!/movie?"
headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {config('API_TOKEN')}"
}

dbname = config('DB_NAME')
user = config('DB_USER')
password = config('DB_PSWD')
host = config('DB_HOST')

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

    def search_movies(self, 
        genres_included=None, genres_excluded=None, keywords_included=None, 
        keywords_excluded=None, actors=None, director=None, title_part=None, 
        country=None, release_date_gte=None, release_date_lte=None,
        order_by=None, order_dir=None):

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
        query += sql.SQL(f" ORDER BY m.{order_by} {order_dir}")

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
    
    def get_actor_names(self, actor_ids: list[int]) -> list[str]:
        if not actor_ids:
            return []
        query = sql.SQL("SELECT (name || ' ' || surname) as name FROM actors WHERE id IN %s")
        rows = self.db_request(query, params=(tuple(actor_ids),))
        return [row['name'] for row in rows]
    
    def get_director_name(self, director_id: int) -> list[str]:
        if director_id:
            query = sql.SQL("SELECT (name || ' ' || surname) as name FROM directors WHERE id = %s")
            rows = self.db_request(query, params=(director_id,))
            return rows[0].get('name')
    
    def get_country_name(self, country_id: int = None, alpha2: str = None) -> list[str]:
        if country_id:
            query = sql.SQL("SELECT name FROM countries WHERE id = %s")
            rows = self.db_request(query, params=(country_id,))
            return rows[0].get('name')
        
        elif alpha2:
            query = sql.SQL("SELECT id FROM countries WHERE alpha2 = %s")
            rows = self.db_request(query, params=(alpha2,))
            return rows[0].get('id')

    def get_genre_names(self, genre_ids: list[int]) -> list[str]:
        if not genre_ids:
            return []
        query = sql.SQL("SELECT name FROM genres WHERE id IN %s")
        rows = self.db_request(query, params=(tuple(genre_ids),))
        return [row['name'] for row in rows]

    def get_keyword_names(self, keyword_ids: list[int]) -> list[str]:
        if not keyword_ids:
            return []
        query = sql.SQL("SELECT name FROM keywords WHERE id IN %s")
        rows = self.db_request(query, params=(tuple(keyword_ids),))
        return [row['name'] for row in rows]
    
    def add_to_list(self, user_id: int, movie_id: int, list_name: str):
        self.db_request(f"INSERT INTO {list_name} (user_id, movie_id) VALUES ({user_id}, {movie_id})", False)

    def remove_from_list(self, user_id: int, movie_id: int, list_name: str):
        self.db_request(f"DELETE FROM {list_name} WHERE user_id = {user_id} AND movie_id = {movie_id}", False)

    def is_in_list(self, user_id: int, movie_id: int, list_name: str) -> bool:
        result = self.db_request(f"SELECT 1 FROM {list_name} WHERE user_id = {user_id} AND movie_id = {movie_id}")
        return bool(result)
    
    def get_params_by_page(self, param_name: str, page: int = 0, page_len: int = 10, get_all: bool = False) -> list[dict]:
        attrs = 'id, name'
        match param_name:
            case 'actors' | 'director':
                attrs = "id, (name || ' ' || surname) as name"
        match param_name:
            case 'director':
                param_name += 's'
            case 'country':
                param_name = 'countries'
        if get_all:
            query = f"SELECT {attrs} FROM {param_name}"
        else:
            query = f"SELECT {attrs} FROM {param_name} LIMIT {page_len} OFFSET {page * page_len}"
        return self.db_request(query)
    
    def get_movies_from_list(self, user_id: int, list_name: str) -> list[dict]:
        query = f"""
        SELECT m.id, m.name, m.release_date, m.release_country, m.poster_link, m.rating, m.revenue, m.runtime, m.director, m.overview,
               array_agg(DISTINCT a.id) AS actors,
               array_agg(DISTINCT g.id) AS genres,
               array_agg(DISTINCT k.id) AS keywords
        FROM movies m
        LEFT JOIN {list_name} fm ON m.id = fm.movie_id
        LEFT JOIN movies_actors ma ON m.id = ma.movie_id
        LEFT JOIN actors a ON ma.actor_id = a.id
        LEFT JOIN movies_genres mg ON m.id = mg.movie_id
        LEFT JOIN genres g ON mg.genre_id = g.id
        LEFT JOIN movies_keywords mk ON m.id = mk.movie_id
        LEFT JOIN keywords k ON mk.keyword_id = k.id
        WHERE fm.user_id = {user_id}
        GROUP BY m.id
        """
        rows = self.db_request(query)
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
                'runtime': row['runtime'],
                'director': row['director'],
                'overview': row['overview'],
                'actors': row['actors'],
                'genres': row['genres'],
                'keywords': row['keywords']
            }
            movies.append(movie)
        return movies
    
    def save_movie(self, movie_data: dict, is_new: bool):
        if not is_new:
            query = sql.SQL('''
                UPDATE movies 
                SET name = %s, release_date = %s, release_country = %s, poster_link = %s, 
                    rating = %s, revenue = %s, runtime = %s, director = %s, overview = %s
                WHERE id = %s
            ''')
        else:
            query = sql.SQL('''
            INSERT INTO movies (name, release_date, release_country, poster_link, 
                rating, revenue, runtime, director, overview)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            
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
        ]
        if not is_new:
            params.append(movie_data.get('id'))
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
    
    def set_movie_score(self, user_id: int, movie_id: int, score: int):
        self.db_request(f"""
            INSERT INTO movies_scores (user_id, movie_id, score)
            VALUES ({user_id}, {movie_id}, {score})
            ON CONFLICT (user_id, movie_id) DO UPDATE
            SET score = EXCLUDED.score
        """, False)

    def get_movie_score(self, movie_id: int, user_id: int):
        result = self.db_request(f"""
            SELECT score FROM movies_scores WHERE
            user_id = {user_id} AND movie_id = {movie_id}
        """)
        if bool(result):
            return result[0].get('score')
        return 0
    
    def get_movie_rating(self, movie_id: int):
        result = self.db_request(f"""
                SELECT rating FROM movies WHERE
                id = {movie_id}
            """)
        if bool(result):
            return result[0].get('rating')
        return 0

    def update_query(self, user_id, film_name, lower_date, upper_date, film_release_country, director, date, actors, genres, genres_no, keywords, keywords_no):
        params = {
            'user_id': user_id,
            'movie_name': film_name,
            'lower_date': lower_date,
            'upper_date': upper_date,
            'movie_release_country': film_release_country,
            'director': director,
            'date': date
        }

        filtered_params = {k: v for k, v in params.items() if v is not None}

        columns = ', '.join(filtered_params.keys())
        placeholders = ', '.join(['%s'] * len(filtered_params))
        query = f"""
            INSERT INTO queries ({columns})
            VALUES ({placeholders})
            RETURNING id;
        """

        result = self.db_request(query, params=tuple(filtered_params.values()))
        query_id = result[0].get('id')

        for actor_id in actors or []:
            self.db_request("""
                INSERT INTO query_actors (query_id, actor_id)
                VALUES (%s, %s);
            """, get=False, params=(query_id, actor_id))

        for genre_id in genres or []:
            self.db_request("""
                INSERT INTO query_genres (query_id, genre_id)
                VALUES (%s, %s);
            """, get=False, params=(query_id, genre_id))

        for genre_id in genres_no or []:
            self.db_request("""
                INSERT INTO query_genres_no (query_id, genre_id)
                VALUES (%s, %s);
            """, get=False, params=(query_id, genre_id))

        for keyword_id in keywords or []:
            self.db_request("""
                INSERT INTO query_keywords (query_id, keyword_id)
                VALUES (%s, %s);
            """, get=False, params=(query_id, keyword_id))

        for keyword_id in keywords_no or []:
            self.db_request("""
                INSERT INTO query_keywords_no (query_id, keyword_id)
                VALUES (%s, %s);
            """, get=False, params=(query_id, keyword_id))
            
    def get_stats(self) -> dict[str, int | dict]:
        # Основная статистика
        usr_cnt = len(self.db_request('SELECT * FROM users'))
        query_month = len(self.db_request("SELECT * FROM queries WHERE date > CURRENT_DATE - '1 month'::interval"))
        query_week = len(self.db_request("SELECT * FROM queries WHERE date > CURRENT_DATE - '1 week'::interval"))
        query_day = len(self.db_request("SELECT * FROM queries WHERE date > CURRENT_DATE - '1 day'::interval"))
        favorite = len(self.db_request("SELECT * FROM favorite_movies"))
        watchlist = len(self.db_request("SELECT * FROM watchlist"))

        # Статистика по актёрам, ключевым словам, жанрам и режиссёрам
        def get_param_stats(table_name: str, interval: str) -> dict[str, int]:
            """Возвращает статистику по параметрам (актёры, ключевые слова, жанры) за указанный интервал."""
            query = f"""
                SELECT {table_name}.name, COUNT(*) as count
                FROM queries
                JOIN query_{table_name} ON queries.id = query_{table_name}.query_id
                JOIN {table_name} ON query_{table_name}.{table_name[:-1]}_id = {table_name}.id
                WHERE queries.date > CURRENT_DATE - '{interval}'::interval
                GROUP BY {table_name}.name
                ORDER BY count DESC
                LIMIT 3
            """
            results = self.db_request(query)
            return [row['name'] for row in results]

        def get_actor_stats(interval: str) -> dict[str, int]:
            """Возвращает статистику по актёрам за указанный интервал."""
            query = f"""
                SELECT actors.name, actors.surname, COUNT(*) as count
                FROM queries
                JOIN query_actors ON queries.id = query_actors.query_id
                JOIN actors ON query_actors.actor_id = actors.id
                WHERE queries.date > CURRENT_DATE - '{interval}'::interval
                GROUP BY actors.name, actors.surname
                ORDER BY count DESC
                LIMIT 3
            """
            results = self.db_request(query)
            return [f"{row['name']} {row['surname']}" for row in results]

        def get_director_stats(interval: str) -> dict[str, int]:
            """Возвращает статистику по режиссёрам за указанный интервал."""
            query = f"""
                SELECT directors.name, directors.surname, COUNT(*) as count
                FROM queries
                JOIN directors ON queries.director = directors.id
                WHERE queries.date > CURRENT_DATE - '{interval}'::interval
                GROUP BY directors.name, directors.surname
                ORDER BY count DESC
                LIMIT 3
            """
            results = self.db_request(query)
            return [f"{row['name']} {row['surname']}" for row in results]

        # Сбор статистики за день, неделю и месяц
        user_queries_day = {
            'actors': get_actor_stats('1 day'),
            'keywords': get_param_stats('keywords', '1 day'),
            'genres': get_param_stats('genres', '1 day'),
            'directors': get_director_stats('1 day'),
        }

        user_queries_week = {
            'actors': get_actor_stats('1 week'),
            'keywords': get_param_stats('keywords', '1 week'),
            'genres': get_param_stats('genres', '1 week'),
            'directors': get_director_stats('1 week'),
        }

        user_queries_month = {
            'actors': get_actor_stats('1 month'),
            'keywords': get_param_stats('keywords', '1 month'),
            'genres': get_param_stats('genres', '1 month'),
            'directors': get_director_stats('1 month'),
        }

        # Возвращаем все данные
        return {
            'usr_cnt': usr_cnt,
            'query_month': query_month,
            'query_week': query_week,
            'query_day': query_day,
            'favorite': favorite,
            'watchlist': watchlist,
            'user_queries_day': user_queries_day,
            'user_queries_week': user_queries_week,
            'user_queries_month': user_queries_month,
        }
    
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
    
    def get_personal_recommendations(self, user_id: int) -> list[dict]:
        preferences_query = """
            SELECT movie_id FROM movies_scores WHERE user_id = %s
            UNION
            SELECT movie_id FROM favorite_movies WHERE user_id = %s;
        """
        preferences = self.db_request(preferences_query, params=(user_id, user_id))
        
        if not preferences:
            return []

        features_query = """
            WITH preferred_features AS (
                SELECT 
                    mg.genre_id AS feature_id,
                    'genre' AS feature_type,
                    COUNT(*) AS score
                FROM movies_genres mg
                WHERE mg.movie_id IN %s
                GROUP BY mg.genre_id
                
                UNION ALL
                
                SELECT 
                    mk.keyword_id AS feature_id,
                    'keyword' AS feature_type,
                    COUNT(*) AS score
                FROM movies_keywords mk 
                WHERE mk.movie_id IN %s
                GROUP BY mk.keyword_id
                
                UNION ALL
                
                SELECT 
                    ma.actor_id AS feature_id,
                    'actor' AS feature_type,
                    COUNT(*) AS score 
                FROM movies_actors ma
                WHERE ma.movie_id IN %s
                GROUP BY ma.actor_id
            )
            SELECT feature_id, feature_type
            FROM preferred_features
            ORDER BY score DESC
            LIMIT 10;
        """
        movie_ids = tuple([pref['movie_id'] for pref in preferences])
        top_features = self.db_request(features_query, params=(movie_ids, movie_ids, movie_ids))

        if not top_features:
            return []

        feature_ids_by_type = {
            'genre': [],
            'keyword': [],
            'actor': []
        }
        for feature in top_features:
            feature_ids_by_type[feature['feature_type']].append(feature['feature_id'])

        movies_query = """
            SELECT DISTINCT m.*
            FROM movies m
            LEFT JOIN movies_genres mg ON mg.movie_id = m.id
            LEFT JOIN movies_keywords mk ON mk.movie_id = m.id
            LEFT JOIN movies_actors ma ON ma.movie_id = m.id
            WHERE 
                (mg.genre_id IN %s OR %s = FALSE) AND
                (mk.keyword_id IN %s OR %s = FALSE) AND
                (ma.actor_id IN %s OR %s = FALSE)
                AND m.id NOT IN %s
            ORDER BY m.rating DESC
            LIMIT 3;
        """
        genre_ids = tuple(feature_ids_by_type['genre']) if feature_ids_by_type['genre'] else (0,)
        keyword_ids = tuple(feature_ids_by_type['keyword']) if feature_ids_by_type['keyword'] else (0,)
        actor_ids = tuple(feature_ids_by_type['actor']) if feature_ids_by_type['actor'] else (0,)
        exclude_movie_ids = tuple([pref['movie_id'] for pref in preferences]) if preferences else (0,)

        recommended_movies = self.db_request(
            movies_query,
            params=(
                genre_ids, not feature_ids_by_type['genre'],
                keyword_ids, not feature_ids_by_type['keyword'],
                actor_ids, not feature_ids_by_type['actor'],
                exclude_movie_ids
            )
        )

        return recommended_movies