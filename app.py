import requests
import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap

url = "https://api.themoviedb.org/3/discover/movie?"

headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIxMjQ3YTcwYmZmYmYzZGZhMWQzNDAxMWEyOWE4ZjdkMyIsInN1YiI6IjY1ZWMwODhlOWQ4OTM5MDE2MjI5OTM4NCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.OxTkKEPFIGD_iIm522Tj18ERii7aE3Su9_Uc996u3yw"
}

genres = [
    {
      "id": 28,
      "name": "боевик"
    },
    {
      "id": 12,
      "name": "приключения"
    },
    {
      "id": 16,
      "name": "мультфильм"
    },
    {
      "id": 35,
      "name": "комедия"
    },
    {
      "id": 80,
      "name": "криминал"
    },
    {
      "id": 99,
      "name": "документальный"
    },
    {
      "id": 18,
      "name": "драма"
    },
    {
      "id": 10751,
      "name": "семейный"
    },
    {
      "id": 14,
      "name": "фэнтези"
    },
    {
      "id": 36,
      "name": "история"
    },
    {
      "id": 27,
      "name": "ужасы"
    },
    {
      "id": 10402,
      "name": "музыка"
    },
    {
      "id": 9648,
      "name": "детектив"
    },
    {
      "id": 10749,
      "name": "мелодрама"
    },
    {
      "id": 878,
      "name": "фантастика"
    },
    {
      "id": 10770,
      "name": "телевизионный фильм"
    },
    {
      "id": 53,
      "name": "триллер"
    },
    {
      "id": 10752,
      "name": "военный"
    },
    {
      "id": 37,
      "name": "вестерн"
    }
  ]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gray = '#353535'
        self.gray2 = '#848483'
        self.white = '#ffffff'
        self.yellow = '#ffbf69'
        self.orange = '#fcac3c'
        self.setWindowTitle("Reelcollator")
        self.setStyleSheet('background-color: %s' % self.gray)
        self.page_num = 1
        self.adult_inc = 'false'
        self.lang = 'ru'
        self.sort_param = 'popularity.desc'
        self.release_year = 'None'
        self.genres_ids = ''
        self.ui()

    def ui(self):
        greeting = QLabel(self, text='Поиск фильмов по жанрам 🔎')
        greeting.setGeometry(QRect(60, 30, 1800, 100))
        greeting.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        greeting_font = greeting.font()
        greeting_font.setPointSize(35)
        greeting_font.setBold(True)
        greeting.setFont(greeting_font)
        greeting.setStyleSheet('color: %s' % self.white)
        search_btn = QPushButton(self, text='Найти')
        search_btn.setGeometry(QRect(800, 1000, 320, 100))
        search_btn.setStyleSheet("""QPushButton {
                            background-color: %s;
                            color: %s;
                            border-radius: 10px
                        }  
                            QPushButton:hover {
                            background-color: %s;   
                        }""" % (self.yellow, self.white, self.orange))
        search_btn_font = greeting.font()
        search_btn_font.setBold(True)
        search_btn_font.setPointSize(20)
        search_btn.setFont(search_btn_font)
        search_btn.clicked.connect(self.search)
        self.chckbxs_lst = []
        for genre in genres:
            genre_name = genre['name']
            globals()['genre_' + genre_name] = QCheckBox(self, text=f'{genre_name}'.title())
            self.chckbxs_lst.append(globals()['genre_' + genre_name])
        del genre_name
        posy = 200
        posx = 50
        cnt = 0
        for widget in self.chckbxs_lst:
            cnt += 1
            widget.setGeometry(QRect(posx, posy, 600, 70))
            widget.setStyleSheet('color: %s' % self.white)
            widget.setFont(search_btn_font)
            widget.setIconSize(QSize(70, 70))
            posy += 70
            if cnt == 10:
                posx += 600
                posy = 200
        del posy
        result_text = QLabel(self, text='Результаты: ')
        result_text.setStyleSheet('color: %s; background-color: %s' % (self.white, self.gray))
        result_text.setFont(search_btn_font)
        result_text.setGeometry(1250, 200, 600, 70)
        self.resultbox = QLabel(self)
        self.resultbox.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.resultbox.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.resultbox.setWordWrap(True)
        resultbox_font = search_btn.font()
        resultbox_font.setPointSize(15)
        self.resultbox.setFont(resultbox_font)
        self.resultbox.setStyleSheet('border-radius: 10px; color: %s; background-color: %s' % (self.gray, self.white))
        scrlarea = QScrollArea(self)
        scrlarea.setWidget(self.resultbox)
        scrlarea.setWidgetResizable(True)
        scrlarea.setGeometry(1250, 270, 600, 600)
        self.page_text = QLabel(self, text='Страница 1')
        self.page_text.setStyleSheet('color: %s; background-color: %s' % (self.white, self.gray))
        self.page_text.setFont(search_btn_font)
        self.page_text.setGeometry(1250, 910, 600, 100)
        self.page_text.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.page_prev_btn = QPushButton(self, text='<')
        self.page_prev_btn.setStyleSheet("""QPushButton {
                            background-color: %s;
                            color: %s;
                            border-radius: 50px
                        }  
                            QPushButton:hover {
                            background-color: %s;   
                        }""" % (self.gray, self.white, self.gray2))
        self.page_prev_btn.setFont(search_btn_font)
        self.page_prev_btn.setGeometry(1300, 880, 100, 100)
        self.page_prev_btn.clicked.connect(self.page_prev)
        self.page_prev_btn.setDisabled(True)
        self.page_next_btn = QPushButton(self, text='>')
        self.page_next_btn.setStyleSheet("""QPushButton {
                            background-color: %s;
                            color: %s;
                            border-radius: 50px
                        }  
                            QPushButton:hover {
                            background-color: %s;   
                        }""" % (self.gray, self.white, self.gray2))
        self.page_next_btn.setFont(search_btn_font)
        self.page_next_btn.setGeometry(1700, 880, 100, 100)
        self.page_next_btn.clicked.connect(self.page_next)
        self.page_next_btn.setDisabled(True)
        self.page_reset = True

    def isThereAnyGenres(self):
        for box in self.chckbxs_lst:
            if box.isChecked():
                return True
        return False
    
    def page_prev(self):
        self.page_num -= 1
        self.page_reset = False
        self.search()

    def page_next(self):
        self.page_num += 1
        self.page_reset = False
        self.search()

    def search(self):
        global url
        global genres
        url_serach = url
        genres_ids = self.genres_ids
        if self.isThereAnyGenres:
            for box in self.chckbxs_lst:
                if box.isChecked():
                    for genre in genres:
                        if genre['name'] == box.text().lower():
                            genres_ids += str(genre['id']) + ','
        self.search_param = [f'page={self.page_num}', f'include_adult={self.adult_inc}', f'language={self.lang}', f'with_genres={genres_ids}', f'sort_by={self.sort_param}']
        for param in self.search_param:
            if 'None' in param:
                continue
            url_serach += '&' + param
        response = requests.get(url=url_serach, headers=headers)
        self.result = ''
        for film in response.json()['results']:
            self.result += film['title'] + '\n\n'
        if self.page_reset:
            self.page_num = 1
        if self.result == '':
            if not self.page_reset:
                self.page_num -= 1
                self.page_next_btn.setDisabled(True)
            else:
                self.resultbox.setStyleSheet('border-radius: 10px; color: %s; background-color: %s' % (self.orange, self.white))
                self.resultbox.setText('По Вашему запросу ничего не было найдено\n\nПопробуйте указать другое сочетание жанров')
                self.page_prev_btn.setDisabled(True)
                self.page_next_btn.setDisabled(True)
                self.page_num = 1
        else:
            self.resultbox.setStyleSheet('border-radius: 10px; color: %s; background-color: %s' % (self.gray, self.white))
            self.resultbox.setText(self.result)
            if not self.page_num == 1:
                self.page_prev_btn.setDisabled(False)
            else:
                self.page_prev_btn.setDisabled(True)
            self.page_next_btn.setDisabled(False)
        self.page_text.setText('Страница ' + str(self.page_num))
        self.page_reset = True

app = QApplication(sys.argv)
main_window = MainWindow()
main_window.setWindowFlag(Qt.FramelessWindowHint)
main_window.showMaximized()
sys.exit(app.exec_())