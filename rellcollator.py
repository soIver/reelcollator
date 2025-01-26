import sys, asyncio
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import QSvgWidget
from data_provider import DataProvider
from collections import deque

class ImageLoader(QRunnable):
    def __init__(self, fid, poster_path, title, rating, callback):
        super().__init__()
        self.fid = fid
        self.poster_path = poster_path
        self.title = title
        self.rating = rating
        self.callback = callback

    def run(self):
        image_data = data_provider.get_image_bin(self.poster_path)
        pixmap = self.__pixmap_from_bytes(image_data)
        QMetaObject.invokeMethod(self.callback, "add_film_card", Qt.QueuedConnection, Q_ARG(int, self.fid), Q_ARG(QPixmap, pixmap), Q_ARG(str, self.title), Q_ARG(str, self.rating))

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
        self.setMaximumSize(600, 900)

    def setPixmap(self, pixmap):
        self.pixmap_original = pixmap
        self.resize(pixmap.size())
        super().setPixmap(self.scaledPixmap())

    def scaledPixmap(self):
        if self.pixmap_original is None:
            return QPixmap()

        width = self.width()
        height = self.height()

        return self.pixmap_original.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap_original:
            self.setPixmap(self.pixmap_original)

class ParameterPanel(QWidget):
    def __init__(self, name: str, placeholder: str, default: str, values: list[dict[str, str | int]], one_value: bool):
        super().__init__()
        self.checked_params: dict[int, list[int, int]] = {}
        self.current_row, self.current_col = 0, 0
        self.values = values
        param_label = QLabel(name)
        completer = QCompleter([value['name'] for value in values])
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.param_edit = QLineEdit(default)
        self.param_edit.setMaximumWidth(300)
        self.param_edit.setPlaceholderText(placeholder)
        self.param_edit.setCompleter(completer)
        self.param_edit.setObjectName('param-edit')
        self.main_lo = QVBoxLayout()
        child_lo = QHBoxLayout()
        if not one_value:
            completer.activated.connect(lambda: self.__update_checked_params(self.param_edit.text()))
            self.param_edit.returnPressed.connect(lambda: self.__update_checked_params(self.param_edit.text()))
            label_lo = QHBoxLayout()
            self.main_lo.addLayout(label_lo)
            if name:
                label_lo.addWidget(param_label)
        else:
            child_lo.addWidget(param_label)
        child_lo.addWidget(self.param_edit)
        child_lo.addStretch()
        self.main_lo.addLayout(child_lo)
        self.setLayout(self.main_lo)

    def __update_checked_params(self, text: str):
        for value in self.values:
            if value['name'] == text:
                if value['id'] not in self.checked_params:
                    self.checked_params[value['id']] = (self.current_row, self.current_col)
                    new_btn = QPushButton()
                    new_btn.setObjectName('deletion')
                    new_btn.setCursor(Qt.PointingHandCursor)
                    new_btn.setFixedSize(40, 40)
                    new_btn.clicked.connect(lambda: self.__delete_param(value['id']))
                    new_btn.setText('×')
                    new_label = QLabel(text)
                    new_label.setAlignment(Qt.AlignCenter)

                    layout = self.main_lo.itemAt(self.current_row + 1)
                    if layout is None:
                        layout = QHBoxLayout()
                        self.main_lo.insertLayout(self.current_row + 1, layout)

                    insert_pos = self.current_col * 2
                    layout.insertWidget(insert_pos, new_btn)
                    layout.insertWidget(insert_pos, new_label)

                    self.current_col += 1
                    if self.current_col == 3:
                        self.current_col = 0
                        self.current_row += 1
                        new_layout = QHBoxLayout()
                        self.main_lo.insertLayout(self.current_row + 1, new_layout)
                        new_layout.addWidget(self.param_edit)
                        new_layout.addStretch()
                    else:
                        layout.insertWidget(layout.count()-2, self.param_edit)
                break
        QTimer.singleShot(0, self.param_edit.clear)
        self.param_edit.setFocus()
        print(self.checked_params)

    def __delete_param(self, id):
        for _ in range(self.current_row + 1):
            layout: QHBoxLayout = self.main_lo.itemAt(1)
            for j in range(layout.count() - 1):
                if layout.itemAt(j).widget() == self.param_edit:
                    layout.removeWidget(layout.itemAt(j).widget())
                else:
                    layout.itemAt(j).widget().deleteLater()
            self.main_lo.removeItem(layout)
        self.current_row, self.current_col = 0, 0
        self.main_lo.insertLayout(1, QHBoxLayout())
        self.main_lo.itemAt(self.current_row + 1).addWidget(self.param_edit)
        self.main_lo.itemAt(1).layout().addStretch()
        self.param_edit.clear()
        self.param_edit.setFocus()
        self.checked_params.pop(id)
        params_ids = self.checked_params.keys()
        self.checked_params = {}
        for key in params_ids:
            for value in self.values:
                if value['id'] == key:
                    self.__update_checked_params(value['name'])
                    break

class FilmPage(QWidget):
    def __init__(self, **fdata):
        super().__init__()
        self.fid = fdata.get('fid', '')
        self.poster_img = fdata.get('poster', '')
        self.title_txt = fdata.get('title', '')
        self.description_txt = fdata.get('description', '')
        self.rating_txt = fdata.get('rating', '')
        details = data_provider.details(self.fid)
        self.release_date = details.get('release_date', '')
        self.revenue = details.get('revenue', '')
        self.runtime = details.get('runtime', '')
        self.description_txt = details.get('overview', '')
        self.release_country = details.get('origin_country', [''])[0]
        self.poster_path = f'https://image.tmdb.org/t/p/original{details.get('poster_path', '')}'
        self.__init_ui()

    def __init_ui(self):
        self.poster = ScaledLabel()
        if self.poster_img:
            self.poster.setPixmap(self.poster_img)
        self.poster_link = QLineEdit(self.poster_path)
        self.rating = QLabel(text=self.rating_txt)
        self.rating.sizeHint = lambda: QSize(247, 60)
        self.date = QLineEdit(self.release_date)
        self.date.sizeHint = lambda: QSize(247, 60)
        self.duration = QLineEdit(str(self.runtime))
        self.duration.sizeHint = lambda: QSize(247, 60)
        self.create_btn = QPushButton('Создать новую карточку фильма')
        self.delete_btn = QPushButton('Удалить')
        self.save_btn = QPushButton('Сохранить')

        self.title = QLineEdit(self.title_txt)
        self.title.setObjectName('title-edit')
        self.description = QPlainTextEdit(self.description_txt)
        country_param = ParameterPanel('Страна:', '', self.release_country, [{'name': 'Россия'}, {'name': 'США'}], True)
        director_param = ParameterPanel('Режиссёр:', '', '', [{'name': 'Лукас', 'id': 1}, {'name': 'Пабло', 'id': 3}], True)
        actors_param = ParameterPanel('Актёры:', '', '', [{'name': 'Лукас', 'id': 1}, {'name': 'Пабло', 'id': 3}], False)
        actors_param = ParameterPanel('Жанры:', '', '', [{'name': 'Лукас', 'id': 1}, {'name': 'Пабло', 'id': 3}], False)
        actors_param = ParameterPanel('Ключевые слова:', '', '', [{'name': 'Лукас', 'id': 1}, {'name': 'Пабло', 'id': 3}], False)

        container = QVBoxLayout()
        container.addWidget(self.description, alignment=Qt.AlignTop)
        container.addWidget(country_param, alignment=Qt.AlignTop)
        container.addWidget(director_param, alignment=Qt.AlignTop)
        container.addWidget(actors_param, alignment=Qt.AlignTop)


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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.poster.setFixedHeight(self.height() - 100)
        
class FilmCard(QWidget):
    def __init__(self, fid: int, title: str, poster: QPixmap, rating: str):
        super().__init__()
        self.fid = fid
        self.title = title
        self.poster = poster
        self.poster_copy = poster
        self.rating = rating
        self.__init_ui()

    def __init_ui(self):
        layout = QVBoxLayout(self)

        self.poster_obj = ScaledLabel()
        self.poster_obj.setPixmap(self.poster)
        self.poster_obj.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.poster_obj.setFixedHeight(500)

        self.title_obj = QLabel(text=self.title)
        self.title_obj.setStyleSheet('font-size: 18pt')
        self.title_obj.setWordWrap(True)

        if float(self.rating) > 0:
            font_size = 18
            text = self.rating
        else:
            font_size = 12
            text = 'нет\nоценок'
        self.rating_obj = QLabel(text=text)
        bg_color = f'rgb({255 - int(float(self.rating)*20)}, {int(float(self.rating)*20)}, 0)' if float(self.rating) > 0 else 'gray'
        self.rating_obj.setStyleSheet(f'font-size: {font_size}pt; padding-left: 5px; padding-right: 5px; border: 2px solid #555; background-color: {bg_color}; border-radius: 5px; color: #fff')
        self.rating_obj.setMaximumSize(100, 60)

        layout.addWidget(self.poster_obj)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.title_obj, stretch=1)
        h_layout.addWidget(self.rating_obj)

        layout.addLayout(h_layout)

        self.poster_obj.setMouseTracking(True)
        self.poster_obj.installEventFilter(self)

    def __open_film_page(self):
        app_window.removeTab(1)
        app_window.insertTab(1, FilmPage(fid = self.fid,
                                         title = self.title,
                                         poster = self.poster_copy,
                                         rating = self.rating), 'Фильм')
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
        self.current_col_genre = 0
        self.current_row_genre = 0
        self.current_col_result = 0
        self.current_row_result = 0
        self.page_num = 1
        self.sort_param = 'popularity.desc'
        self.genres_ids = ''
        self.__initUI()

    def __initUI(self):
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите название фильма')
        self.search_edit.setMinimumHeight(60)

        search_bttn = QPushButton('Поиск')
        search_bttn.setMinimumHeight(60)
        search_bttn.clicked.connect(self.start_search)
        search_bttn.setCursor(Qt.PointingHandCursor)

        self.genres_edit = ParameterPanel('', 'название жанра', '', genres, False)

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

    @pyqtSlot(int, QPixmap, str, str)
    def add_film_card(self, fid, pixmap, title, rating):
        result = FilmCard(fid, title, pixmap, rating)
        self.results_layout.itemAt(self.results_layout.count()-2).insertWidget(self.current_col_result, result, alignment = Qt.AlignTop | Qt.AlignLeft)
        self.results_layout.itemAt(self.results_layout.count()-2).addStretch()
        self.current_col_result += 1
        if self.current_col_result > 2:
            self.current_row_result += 1
            self.current_col_result = 0
            self.results_layout.insertLayout(self.results_layout.count()-1, QHBoxLayout())
        self.process_next_image()

    def process_next_image(self):
        if self.image_queue:
            fid, poster_path, title, rating = self.image_queue.popleft()
            loader = ImageLoader(fid, poster_path, title, rating, self)
            QThreadPool.globalInstance().start(loader)

    async def __search(self):
        search_params = {'page': [str(self.page_num)], 'include_adult': ['false'], 'language': ['ru-RU'], 
                        'query': [self.search_edit.text()]} if self.search_edit.text() else None
        discover_params = {'page': [str(self.page_num)], 'include_adult': ['false'], 'language': ['ru-RU'],
                        'with_genres': [str(id) if self.genres_edit.checked_params[id] else '' for id in self.genres_edit.checked_params.keys()],
                        'sort_by': [self.sort_param]} if self.sort_param else None
        response = data_provider.api_request(search_params, discover_params)

        if response:
            for film in response:
                fid = film['id']
                title = film['title']
                rating = str(round(float(film['vote_average']), 1))
                poster_path = film['poster_path']
                
                self.image_queue.append((fid, poster_path, title, rating))
            self.process_next_image()
        else: 
            print("ошибка")

    def start_search(self):
        self.current_col_result = 0
        self.current_row_result = 0
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
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.results_widget.setFixedWidth(self.results.width()-5)
        self.results_widget.setFixedHeight(self.results.height()//2 * 10)

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
            width: 200%
        }
        QTabBar::tab:selected {
            margin: 15%;
            background-color: #f5f5f5;
        }
        QPlainTextEdit {
            font-size: 16pt;
        }
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
        QLineEdit#param-edit {
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
        QCompleter {
            background-color: #888;
        }
        ''')

data_provider = DataProvider()
genres: list[dict[str, str | int]] = []
for pair in data_provider.db_request('SELECT * FROM genres'):
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