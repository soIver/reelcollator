from dns_client.adapters.requests import DNSClientSession
from contextlib import closing
import psycopg2

def title_encode(url: str):
            encoded_url = ""
            for char in url:
                encoded_char = char.encode('utf-8').hex().upper()
                encoded_url += f"%{encoded_char[:2]}%{encoded_char[2:]}"
            return encoded_url

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
        return self.session.get(url=request.strip('&'), headers=headers).json()['results']
    
    def discover(self, params: dict[str, list[str]]):
        request = base_url.replace('!', '/discover')
        for key, value in params.items():
            request += f'{key}='
            request += ','.join(value) + '&'
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
        session = DNSClientSession('9.9.9.9')
        url = f'https://image.tmdb.org/t/p/original{image_path}'
        response = session.get(url, stream=True, timeout=20)
        return response.content
    
    def db_request(self, query: str):
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
        return result
