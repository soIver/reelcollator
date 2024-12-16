import sys, asyncio
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import QSvgWidget
from data_provider import DataProvider
from collections import deque

class ImageLoader(QRunnable):
    def __init__(self, poster_path, title, rating, callback):
        super().__init__()
        self.poster_path = poster_path
        self.title = title
        self.rating = rating
        self.callback = callback

    def run(self):
        image_data = DataProvider.get_image_bin(self.poster_path)
        pixmap = self.__pixmap_from_bytes(image_data)
        QMetaObject.invokeMethod(self.callback, "add_film_card", Qt.QueuedConnection, Q_ARG(QPixmap, pixmap), Q_ARG(str, self.title), Q_ARG(str, self.rating))

    def __pixmap_from_bytes(self, image_bin):
        byte_array = QByteArray(image_bin)
        pixmap = QPixmap()
        pixmap.loadFromData(byte_array)
        return pixmap
    
class ScaledLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap_original = None
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setStyleSheet('border: 1px solid #ccc;')

    def setPixmap(self, pixmap):
        self.pixmap_original = pixmap
        super().setPixmap(self.scaledPixmap())

    def scaledPixmap(self):
        if self.pixmap_original is None:
            return QPixmap()

        width = self.width()
        height = self.height()

        return self.pixmap_original.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setPixmap(self.pixmap_original)

class FilmPage(QWidget):
    def __init__(self, **fdata):
        super().__init__()
        self.id = fdata.get('id', '')
        self.poster_img = fdata.get('poster', '')
        self.title_txt = fdata.get('title', '')
        self.description_txt = fdata.get('description', '')
        self.rating_txt = fdata.get('rating', '')
        self.__init_ui()

    def __init_ui(self):
        self.setStyleSheet("""
        QWidget#container-param {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 5%;
            padding: 20px;
        }
        QLabel {
            font-size: 15pt;
            font-family: Calibri;
            font-weight: bold;
        }
        QLineEdit {
            font-size: 16pt;
            font-family: Calibri;
            background-color: #fff;
            border: 1px solid #ccc;
            border-radius: 5%;
            padding: 5px;
        }
        QLineEdit#genres-edit {
            font-size: 15pt;
            font-weight: bold;
            background-color: #f0f0f0;
            border: none;
        }
        QLineEdit#title-edit {
            font-size: 24pt;
            font-weight: bold;
            background-color: #f0f0f0;
            border: none;
        }
        QPushButton {
            font-size: 16pt;
            font-family: Calibri;
            background-color: #4CAF50;
            color: #fff;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #3e8e41;
        }
        QPushButton#settings {
            background-color: #bbb;
        }
        QPushButton#settings:hover {
            background-color: #888;
        }
        QPushButton#deletion {
            background-color: #bbb;
            color: #000;
            border-radius: 20px;
            padding: 0;
            font-size: 20pt;
            font-weight: bold
        }
        QPushButton#deletion:hover {
            background-color: #d62828;
            color: #fff
        }
        """)
        self.poster = ScaledLabel()
        if self.poster_img:
            self.poster.setPixmap(self.poster_img)
        self.poster_link = QLineEdit()
        self.rating = QLabel(text=self.rating_txt)
        self.rating.sizeHint = lambda: QSize(247, 60)
        self.date = QLineEdit()
        self.date.sizeHint = lambda: QSize(247, 60)
        self.duration = QLineEdit()
        self.duration.sizeHint = lambda: QSize(247, 60)
        self.create_btn = QPushButton('Создать новую карточку фильма')
        self.delete_btn = QPushButton('Удалить')
        self.save_btn = QPushButton('Сохранить')

        self.title = QLineEdit(self.title_txt)
        self.title.setObjectName('title-edit')
        self.description = QLineEdit(self.description_txt)

        container = QVBoxLayout()
        container.addWidget(self.description, alignment=Qt.AlignTop)
        container_widget = QWidget()
        container_widget.setLayout(container)
        container_area = QScrollArea()
        container_area.setWidgetResizable(True)
        container_area.setWidget(container_widget)

        leftside = QVBoxLayout()
        leftside.addWidget(self.poster, alignment=Qt.AlignHCenter)
        leftside.addWidget(self.poster_link)

        rightside = QVBoxLayout()
        rightside.addWidget(self.title)
        rightside.addWidget(container_area)

        botside = QHBoxLayout()
        botside.addWidget(rating_svg)
        botside.addWidget(self.rating)
        botside.addWidget(date_svg)
        botside.addWidget(self.date)
        botside.addWidget(duration_svg)
        botside.addWidget(self.duration)
        botside.addWidget(self.create_btn)
        botside.addStretch()
        botside.addWidget(self.delete_btn)
        botside.addWidget(self.save_btn)

        topside = QHBoxLayout()
        topside.addLayout(leftside)
        topside.addLayout(rightside)

        layout = QVBoxLayout()
        layout.addLayout(topside)
        layout.addLayout(botside)
        self.setLayout(layout)
        
class FilmCard(QWidget):
    def __init__(self, title, poster, rating):
        super().__init__()
        self.title = title
        self.poster = poster
        self.poster_copy = poster
        self.rating = rating
        self.__init_ui()

    def __init_ui(self):
        layout = QVBoxLayout(self)  # Устанавливаем layout для виджета

        self.poster_obj = ScaledLabel()
        self.poster_obj.setPixmap(self.poster)
        self.poster_obj.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.poster_obj.setFixedHeight(500)

        self.title_obj = QLabel(text=self.title)
        self.title_obj.setStyleSheet('font-size: 18pt')
        self.title_obj.setWordWrap(True)

        self.rating_obj = QLabel(text=self.rating if float(self.rating) > 0 else 'нет\nоценок')
        bg_color = f'rgb({255 - int(float(self.rating)*20)}, {int(float(self.rating)*20)}, 0)' if float(self.rating) > 0 else 'gray'
        self.rating_obj.setStyleSheet(f'font-size: 18pt; padding-left: 5px; padding-right: 5px; border: 2px solid #555; background-color: {bg_color}; border-radius: 5px; color: #fff')
        self.rating_obj.setMaximumSize(80, 60)

        layout.addWidget(self.poster_obj)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.title_obj, stretch=1)
        h_layout.addWidget(self.rating_obj)

        layout.addLayout(h_layout)

        self.poster_obj.setMouseTracking(True)
        self.poster_obj.installEventFilter(self)

    def __open_film_page(self):
        app_window.removeTab(1)
        app_window.insertTab(1, FilmPage(title = self.title,
                                         poster = self.poster_copy,
                                         reting = self.rating), 'Фильм')
        app_window.setCurrentIndex(1)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Enter and source is self.poster_obj:
            self.poster_obj.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=20, xOffset=3, yOffset=2))
        elif event.type() == QEvent.Leave and source is self.poster_obj:
            self.poster_obj.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=0, xOffset=0, yOffset=0))
        elif event.type() == QEvent.MouseButtonPress and source is self.poster_obj:
            self.__open_film_page()
        return super().eventFilter(source, event)

    def delete(self):
        self.title_obj.deleteLater()
        self.rating_obj.deleteLater()
        self.poster_obj.deleteLater()
        self.layout().deleteLater()
        self.deleteLater()

class SearchWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.checked_genres: dict[int, list[int, int]] = {}
        self.current_col_genre = 0
        self.current_row_genre = 0
        self.current_col_result = 0
        self.current_row_result = 0
        self.page_num = 1
        self.sort_param = 'popularity.desc'
        self.genres_ids = ''
        self.__initUI()

    def __initUI(self):
        self.setStyleSheet("""
        QWidget#container-param {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 5%;
            padding: 20px;
        }
        QLabel {
            font-size: 15pt;
            font-family: Calibri;
            font-weight: bold;
        }
        QLineEdit {
            font-size: 16pt;
            font-family: Calibri;
            background-color: #fff;
            border: 1px solid #ccc;
            border-radius: 5%;
            padding: 5px;
        }
        QLineEdit#genres-edit {
            font-size: 15pt;
            font-weight: bold;
            background-color: #f0f0f0;
            border: none;
        }
        QPushButton {
            font-size: 16pt;
            font-family: Calibri;
            background-color: #4CAF50;
            color: #fff;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #3e8e41;
        }
        QPushButton#settings {
            background-color: #bbb;
        }
        QPushButton#settings:hover {
            background-color: #888;
        }
        QPushButton#deletion {
            background-color: #bbb;
            color: #000;
            border-radius: 20px;
            padding: 0;
            font-size: 20pt;
            font-weight: bold
        }
        QPushButton#deletion:hover {
            background-color: #d62828;
            color: #fff
        }
        QCompleter {
            background-color: #888;
        }
        """)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите название фильма')
        self.search_edit.setMinimumHeight(60)

        search_bttn = QPushButton('Поиск')
        search_bttn.setMinimumHeight(60)
        search_bttn.clicked.connect(self.start_search)
        search_bttn.setCursor(Qt.PointingHandCursor)

        self.genres_edit = QLineEdit()
        completer = QCompleter([genre['name'].lower() for genre in genres])
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        completer.activated.connect(lambda: self.__update_checked_genres(self.genres_edit.text()))
        self.genres_edit.setCompleter(completer)
        self.genres_edit.setPlaceholderText('название жанра')
        self.genres_edit.returnPressed.connect(lambda: self.__update_checked_genres(self.genres_edit.text()))
        self.genres_edit.setObjectName('genres-edit')
        self.genres_edit.setMaximumWidth(300)
        self.genres_edit.setAlignment(Qt.AlignVCenter)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.search_edit)
        h_layout.addWidget(search_bttn)
        h_layout.setStretch(0, 8)
        h_layout.setStretch(1, 1)

        self.v_layout = QVBoxLayout()
        self.v_layout.addLayout(h_layout)
        self.v_layout.addLayout(QHBoxLayout())
        self.v_layout.itemAt(1).addWidget(self.genres_edit)
        self.v_layout.itemAt(1).addStretch()
        self.v_layout.addStretch()
        
        self.results_layout = QVBoxLayout()
        self.results_widget = QWidget()
        self.results = QScrollArea()
        self.results.setWidgetResizable(True)
        self.results.setWidget(self.results_widget)

        main_layout = QHBoxLayout()
        main_layout.addLayout(self.v_layout)
        main_layout.addWidget(self.results)
        main_layout.setStretch(0, 2)
        main_layout.setStretch(1, 3)
        self.setLayout(main_layout)
        self.results_widget.setLayout(self.results_layout)
        self.results_layout.addLayout(QHBoxLayout())
        self.results_layout.addStretch()

    def __update_checked_genres(self, text):
        for genre in genres:
            if genre['name'].lower() == text.lower():
                if genre['id'] not in self.checked_genres.keys():
                    self.checked_genres[genre['id']] = [self.current_row_genre, self.current_col_genre]
                    insert_pos = self.current_col_genre * 2
                    new_btn = QPushButton(text='×')
                    new_btn.setCursor(Qt.PointingHandCursor)
                    new_label = QLabel(text)
                    new_label.setAlignment(Qt.AlignVCenter|Qt.AlignHCenter)
                    new_btn.setObjectName('deletion')
                    new_btn.setFixedSize(40, 40)
                    new_btn.clicked.connect(lambda: self.__delete_genre(genre['id']))
                    self.v_layout.itemAt(self.current_row_genre + 1).insertWidget(insert_pos, new_btn)
                    self.v_layout.itemAt(self.current_row_genre + 1).insertWidget(insert_pos, new_label)
                    self.v_layout.itemAt(self.current_row_genre + 1).insertWidget(insert_pos + 2, self.genres_edit)
                    self.current_col_genre += 1
                    if self.current_col_genre == 3:
                        self.current_row_genre += 1
                        self.current_col_genre = 0
                        self.v_layout.insertLayout(self.current_row_genre + 1, QHBoxLayout())
                        self.v_layout.itemAt(self.current_row_genre + 1).addWidget(self.genres_edit)
                        self.v_layout.itemAt(self.current_row_genre + 1).addStretch()
                break
        QTimer.singleShot(0, self.genres_edit.clear)
        self.genres_edit.setFocus()

    def __delete_genre(self, id):
        for _ in range(self.current_row_genre + 1):
            layout: QHBoxLayout = self.v_layout.itemAt(1)
            for j in range(layout.count() - 1):
                if layout.itemAt(j).widget() == self.genres_edit:
                    layout.removeWidget(layout.itemAt(j).widget())
                else:
                    layout.itemAt(j).widget().deleteLater()
            self.v_layout.removeItem(layout)
        self.current_row_genre, self.current_col_genre = 0, 0
        self.v_layout.insertLayout(1, QHBoxLayout())
        self.v_layout.itemAt(self.current_row_genre + 1).addWidget(self.genres_edit)
        self.v_layout.itemAt(1).layout().addStretch()
        self.genres_edit.clear()
        self.genres_edit.setFocus()
        self.checked_genres.pop(id)
        genres_ids = self.checked_genres.keys()
        self.checked_genres = {}
        for key in genres_ids:
            for genre in genres:
                if genre['id'] == key:
                    self.__update_checked_genres(genre['name'].lower())
                    break

    @pyqtSlot(QPixmap, str, str)
    def add_film_card(self, pixmap, title, rating):
        result = FilmCard(title, pixmap, rating)
        self.results_layout.itemAt(self.results_layout.count()-2).insertWidget(self.current_col_result, result)
        self.results_layout.itemAt(self.results_layout.count()-2).addStretch()
        self.current_col_result += 1
        if self.current_col_result > 2:
            self.current_row_result += 1
            self.current_col_result = 0
            self.results_layout.insertLayout(self.results_layout.count()-1, QHBoxLayout())
        self.process_next_image()

    def process_next_image(self):
        if self.image_queue:
            poster_path, title, rating = self.image_queue.popleft()
            loader = ImageLoader(poster_path, title, rating, self)
            QThreadPool.globalInstance().start(loader)

    async def __search(self):
        search_params = {'page': [str(self.page_num)], 'include_adult': ['false'], 'language': ['ru-RU'], 
                        'query': [self.search_edit.text()]} if self.search_edit.text() else None
        discover_params = {'page': [str(self.page_num)], 'include_adult': ['false'], 'language': ['ru-RU'],
                        'with_genres': [str(id) if self.checked_genres[id] else '' for id in self.checked_genres.keys()],
                        'sort_by': [self.sort_param]} if self.checked_genres else None
        response = DataProvider.api_request(search_params, discover_params)

        if response:
            for film in response:
                title = film['title']
                rating = str(round(float(film['vote_average']), 1))
                poster_path = film['poster_path']
                
                self.image_queue.append((poster_path, title, rating))
            self.process_next_image()
        else: 
            print("ошибка")

    def start_search(self):
        self.current_col_result = 0
        self.current_row_result = 0
        res_cnt = self.results_layout.count()
        print(res_cnt)
        self.clear_film_cards(self.results_layout)
        self.results_layout.insertItem(0, QHBoxLayout())
        self.image_queue = deque()
        asyncio.run(self.__search())

    def clear_film_cards(self, widget):
        if isinstance(widget, FilmCard):
            widget.setParent(None)
            widget.deleteLater()
            return

        if isinstance(widget, QLayout):
            for i in reversed(range(widget.count())):
                item = widget.itemAt(i)
                if item.widget():
                    self.clear_film_cards(item.widget())
                elif item.layout():
                    self.clear_film_cards(item.layout())
            return
        
class AppWindow(QTabWidget):
    def __init__(self, **tabs):
        super().__init__()
        self.setWindowTitle("Reelcollator")
        self.setMinimumSize(720, 480)
        
        self.__init_ui()
        for key, value in tabs.items():
          self.addTab(value, str(key))

        for children in self.findChildren(QTabBar):
            children.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=20, xOffset=-3, yOffset=2))
    
    def __init_ui(self):
        self.setStyleSheet('''
        QTabBar::tab {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            font-family: Calibri;
            font-size: 15pt;
            border-radius: 5%;
            margin: 10%;
            height: 50px;
            width: 200px
        }
        QTabBar::tab:selected {
            margin: 15%;
            background-color: #f5f5f5;
        }
        ''')

genres: list[dict[str, str | int]] = []
for pair in DataProvider.db_request('SELECT * FROM genres'):
    genres.append({'id': pair[0], 'name': pair[1]})
app = QApplication(sys.argv)
rating_svg = QSvgWidget('icons/rating.svg')
date_svg = QSvgWidget('icons/date.svg')
duration_svg = QSvgWidget('icons/duration.svg')
rating_svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
date_svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
duration_svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
app_window = AppWindow(Поиск = SearchWindow(), Фильм = FilmPage())
app_window.showMaximized()
sys.exit(app.exec_())