from dns_client.adapters.requests import DNSClientSession
import psycopg2

def title_encode(url: str):
            encoded_url = ""
            for char in url:
                encoded_char = char.encode('utf-8').hex().upper()
                encoded_url += f"%{encoded_char[:2]}%{encoded_char[2:]}"
            return encoded_url

base_url = "https://api.themoviedb.org/3/!/movie?"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxMjQ3YTcwYmZmYmYzZGZhMWQzNDAxMWEyOWE4ZjdkMyIsInN1YiI6IjY1ZWMwODhlOWQ4OTM5MDE2MjI5OTM4NCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.OxTkKEPFIGD_iIm522Tj18ERii7aE3Su9_Uc996u3yw"
}

dbname='2024_psql_rad'
user='2024_psql_r_usr'
password='g9yyJG0bzVNGW3RH'
host='5.183.188.132'

class DataProvider:
    @staticmethod
    def api_request(search_params: dict[str, list[str]] = None, discover_params: dict[str, list[str]] = None):
        discover_response: list[dict] = []
        search_response: list[dict] = []
        session = DNSClientSession('9.9.9.9')
        if search_params:
            request = base_url.replace('!', 'search')
            for key, value in search_params.items():
                request += f'{key}='
                request += ','.join(value) + '&'
            request = request.strip('&')
            search_response = session.get(url=request, headers=headers).json()['results']

        if discover_params:
            request = base_url.replace('!', 'discover')
            for key, value in discover_params.items():
                request += f'{key}='
                request += ','.join(value) + '&'
            request = request.strip('&')
            discover_response = session.get(url=request, headers=headers).json()['results']

        if discover_response and search_response:
            response = [film for film in discover_response if film in search_response]
        elif discover_response: 
            response = discover_response
        elif search_response: 
            response = search_response
        else: 
            response = False
        print(request)
        print(response)
        
        return response
    
    @staticmethod
    def db_request(query: str):
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.commit()
        conn.close()
        return result
