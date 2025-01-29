import sys, asyncio
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import QSvgWidget
from data_provider import DataProvider
from collections import deque
from datetime import date

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
        self.setMaximumSize(600, 900)
        self.setAlignment(Qt.AlignLeft)

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
    def __init__(self, name: str, placeholder: str, default: str, values: dict[str | int, str], one_value: bool):
        super().__init__()
        self.checked_params: dict[int, list[int, int]] = {}
        self.current_row, self.current_col = 0, 0
        self.values = values
        self.one_value = one_value
        param_label = QLabel(name)
        completer = QCompleter([value for value in values.values()])
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.param_edit = QLineEdit(default)
        self.param_edit.setMaximumWidth(300)
        self.param_edit.setPlaceholderText(placeholder)
        self.param_edit.setCompleter(completer)
        self.param_edit.setObjectName('param-edit')
        self.main_lo = QVBoxLayout()
        child_lo = QHBoxLayout()
        completer.activated.connect(lambda: self.__update_checked_params(self.param_edit.text()))
        self.param_edit.returnPressed.connect(lambda: self.__update_checked_params(self.param_edit.text()))
        if not one_value:
            label_lo = QHBoxLayout()
            self.main_lo.addLayout(label_lo)
            if name:
                label_lo.addWidget(param_label)
        else:
            if name:
                child_lo.addWidget(param_label)
        child_lo.addWidget(self.param_edit)
        child_lo.addStretch()
        self.main_lo.addLayout(child_lo)
        self.setLayout(self.main_lo)

    def __update_checked_params(self, text: str):
        for key in self.values.keys():
            if self.values[key] == text:
                if key not in self.checked_params:
                    if self.one_value:
                        self.checked_params = {}
                        self.checked_params[key] = 0
                        return
                    self.checked_params[key] = (self.current_row, self.current_col)
                    new_btn = QPushButton()
                    new_btn.setObjectName('deletion')
                    new_btn.setCursor(Qt.PointingHandCursor)
                    new_btn.setFixedSize(40, 40)
                    new_btn.clicked.connect(lambda: self.__delete_param(key))
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
        for id in params_ids:
            for key in self.values.keys():
                if key == id:
                    self.__update_checked_params(self.values[key])
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
        self.revenue_txt = details.get('revenue', '')
        self.runtime = details.get('runtime', '')
        self.description_txt = details.get('overview', '')
        self.release_country = details.get('origin_country', [''])[0]
        self.poster_path = f'https://image.tmdb.org/t/p/original{details.get('poster_path', '')}'
        self.__init_ui()

    def __init_ui(self):
        self.poster = ScaledLabel()
        if self.poster_img:
            self.poster.setPixmap(self.poster_img)
            self.poster.setAlignment(Qt.AlignCenter)
            
        self.poster_link = QLineEdit(self.poster_path)
        self.rating = QLabel(text=self.rating_txt)
        self.rating.sizeHint = lambda: QSize(247, 60)
        self.date = QLineEdit(self.release_date)
        self.date.sizeHint = lambda: QSize(247, 60)
        self.duration = QLineEdit(str(self.runtime))
        self.duration.sizeHint = lambda: QSize(247, 60)
        self.revenue = QLineEdit(str(self.revenue_txt))
        self.revenue.sizeHint = lambda: QSize(247, 60)
        self.create_btn = QPushButton('Создать новую карточку фильма')
        self.delete_btn = QPushButton('Удалить')
        self.save_btn = QPushButton('Сохранить')

        self.title = QLineEdit(self.title_txt)
        self.title.setObjectName('title-edit')
        self.description = QPlainTextEdit(self.description_txt)
        country_param = ParameterPanel('Страна:', '', self.release_country, countries, True)
        director_param = ParameterPanel('Режиссёр:', '', '', directors, True)
        actors_param = ParameterPanel('Актёры:', '', '', actors, False)
        genres_param = ParameterPanel('Жанры:', '', '', genres, False)
        keywords_param = ParameterPanel('Ключевые слова:', '', '', keywords, False)

        container = QVBoxLayout()
        container.addWidget(self.description, alignment=Qt.AlignTop)
        container.addWidget(country_param, alignment=Qt.AlignTop)
        container.addWidget(director_param, alignment=Qt.AlignTop)
        container.addWidget(actors_param, alignment=Qt.AlignTop)
        container.addWidget(genres_param, alignment=Qt.AlignTop)
        container.addWidget(keywords_param, alignment=Qt.AlignTop)

        container_widget = QWidget()
        container_widget.setLayout(container)
        container_area = QScrollArea()
        container_area.setWidgetResizable(True)
        container_area.setWidget(container_widget)

        botside_l = QGridLayout()
        botside_l.addWidget(icons['rating'], 0, 0)
        botside_l.addWidget(self.rating, 0, 1)
        botside_l.addWidget(icons['date'], 0, 2)
        botside_l.addWidget(self.date, 0, 3)
        botside_l.addWidget(icons['duration'], 1, 0)
        botside_l.addWidget(self.duration, 1, 1)
        botside_l.addWidget(icons['revenue'], 1, 2)
        botside_l.addWidget(self.revenue, 1, 3)

        leftside = QVBoxLayout()
        leftside.addWidget(self.poster, alignment=Qt.AlignHCenter)
        leftside.addWidget(self.poster_link)
        leftside.addLayout(botside_l)

        botside_r = QHBoxLayout()
        botside_r.addWidget(self.create_btn)
        botside_r.addStretch()
        botside_r.addWidget(self.delete_btn)
        botside_r.addWidget(self.save_btn)
        rightside = QVBoxLayout()
        rightside.addWidget(self.title)
        rightside.addWidget(container_area)
        rightside.addLayout(botside_r)

        layout = QHBoxLayout()
        layout.addLayout(leftside)
        layout.addLayout(rightside)

        self.setLayout(layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.poster.setFixedHeight(self.height() - 200)
        self.poster.setFixedWidth(self.width() // 2 - 200)

        
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

class SortButtons(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 'desc'
        self.value_bool = True
        self.disabled_effect = QGraphicsColorizeEffect()
        self.disabled_effect.setColor(QColor(0, 0, 0, 10))  
        self.sort_asc = QPushButton('↑')
        self.sort_asc.clicked.connect(self.__change_value)
        self.sort_desc = QPushButton('↓')
        self.sort_desc.clicked.connect(self.__change_value)
        self.sort_desc.setDisabled(True)
        self.sort_desc.setGraphicsEffect(self.disabled_effect)
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.sort_asc)
        main_layout.addWidget(self.sort_desc)
        self.setLayout(main_layout)

    def __change_value(self):
        self.value_bool = not self.value_bool
        if self.value_bool:
            self.sort_asc.setDisabled(False)
            self.sort_desc.setDisabled(True)
            self.sort_desc.setGraphicsEffect(self.disabled_effect)
        else:
            self.sort_asc.setDisabled(True)
            self.sort_desc.setDisabled(False)
            self.sort_asc.setGraphicsEffect(self.disabled_effect)
        self.value = 'desc' if self.value_bool else 'asc'

class SearchWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.sort_params = {'vote_average': 'рейтингу',
                            'primary_release_date': 'дате выхода',
                            'revenue': 'сумме сборов'}
        self.__initUI()

    def __initUI(self):
        self.disabled_effect = QGraphicsColorizeEffect()
        self.disabled_effect.setColor(QColor(0, 0, 0, 10))
        self.effect_spot = QWidget()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите название фильма')
        self.search_edit.setMinimumHeight(60)

        self.search_bttn = QPushButton('Поиск')
        self.search_bttn.setMinimumHeight(60)
        self.search_bttn.clicked.connect(self.start_search)
        self.search_bttn.setCursor(Qt.PointingHandCursor)

        sort_label = QLabel('Сортировать результаты по')
        self.sort_panel = ParameterPanel('', '', '', self.sort_params, True)
        self.sort_panel.setMinimumWidth(250)
        self.sort_panel.setObjectName('param-edit')
        self.sort_asc_desc = SortButtons()

        self.director_panel = ParameterPanel('', 'режиссёр', '', directors, True)
        self.country_panel = ParameterPanel('', 'страна', '', countries, True)
        self.date_edit = QLineEdit(self)
        self.date_edit.setInputMask("00.00.0000-00.00.0000;_")
        self.date_edit.setObjectName('param-edit')
        today = date.today()
        today = today.strftime("%d.%m.%Y")
        self.date_edit.setText(f"28.12.1895-{today}")

        self.genres_panel = ParameterPanel('', 'с жанром', '', genres, False)
        self.genres_panel_no = ParameterPanel('', 'без жанра', '', genres, False)
        self.keywords_panel = ParameterPanel('', 'с ключевым словом', '', keywords, False)
        self.keywords_panel_no = ParameterPanel('', 'без ключевого слова', '', keywords, False)
        self.actors_panel = ParameterPanel('', 'с актёром', '', actors, False)

        searchbox_layout = QHBoxLayout()
        searchbox_layout.addWidget(self.search_edit)
        searchbox_layout.addWidget(self.search_bttn)
        searchbox_layout.setStretch(0, 8)
        searchbox_layout.setStretch(1, 1)

        sort_layout = QHBoxLayout()
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_panel)
        sort_layout.addWidget(self.sort_asc_desc)

        edits_layout = QHBoxLayout()
        edits_layout.addWidget(self.director_panel)
        edits_layout.addWidget(self.country_panel)
        edits_layout.addWidget(self.date_edit)

        self.v_layout = QVBoxLayout()
        self.v_layout.addLayout(searchbox_layout)
        self.v_layout.addLayout(sort_layout)
        self.v_layout.addLayout(edits_layout)
        self.v_layout.addWidget(self.genres_panel)
        self.v_layout.addWidget(self.genres_panel_no)
        self.v_layout.addWidget(self.keywords_panel)
        self.v_layout.addWidget(self.keywords_panel_no)
        self.v_layout.addWidget(self.actors_panel)
        self.v_layout.addStretch()
        
        self.results = ResultsPanel()

        main_layout = QHBoxLayout()
        main_layout.addLayout(self.v_layout)
        main_layout.addWidget(self.results)
        
        main_layout.setStretch(0, 2)
        main_layout.setStretch(1, 3)
        self.setLayout(main_layout)

    @pyqtSlot(int, QPixmap, str, str)
    def add_film_card(self, fid, pixmap, title, rating):
        result = FilmCard(fid, title, pixmap, rating)
        self.results.results_layout.itemAt(self.results.results_layout.count()-2).insertWidget(self.results.current_col_result, result, alignment = Qt.AlignTop | Qt.AlignLeft)
        self.results.results_layout.itemAt(self.results.results_layout.count()-2).addStretch()
        self.results.current_col_result += 1
        if self.results.current_col_result > 2:
            self.results.current_row_result += 1
            self.results.current_col_result = 0
            self.results.results_layout.insertLayout(self.results.results_layout.count()-1, QHBoxLayout())
        self.process_next_image()

    def process_next_image(self):
        if self.image_queue:
            if self.results.film_cnt > 8:
                self.results.film_cnt = 0
                self.results.current_col_result = 0
                self.results.current_row_result = 0
                self.results.add_page()

            fid, poster_path, title, rating = self.image_queue.popleft()
            loader = ImageLoader(fid, poster_path, title, rating, self)
            QThreadPool.globalInstance().start(loader)
            self.results.film_cnt += 1
    
    def show_msg(self, msg: str):
        print(msg)

    async def __search(self):
        release_date_gte, release_date_lte = self.date_edit.text().split('-')
        release_date_gte, release_date_lte = release_date_gte.split('.'), release_date_lte.split('.')
        release_date_gte.reverse()
        release_date_lte.reverse()
        if int(''.join(release_date_gte)) > int(''.join(release_date_lte)):
            self.show_msg('Первая дата интервала выхода фильма не может быть больше второй')
        search_params = {'page': [str(self.results.page_cnt)], 'include_adult': ['false'], 'language': ['ru-RU'], 
                        'query': [self.search_edit.text()]} if self.search_edit.text() else None
        discover_params = {'page': [str(self.results.page_cnt)], 'include_adult': ['false'], 'language': ['ru-RU'],
                        'with_genres': [str(id) for id in self.genres_panel.checked_params.keys()],
                        'without_genres': [str(id) for id in self.genres_panel_no.checked_params.keys()],
                        'with_keywords': [str(id) for id in self.keywords_panel.checked_params.keys()],
                        'without_keywords': [str(id) for id in self.keywords_panel_no.checked_params.keys()],
                        'with_people': [str(id) for id in self.actors_panel.checked_params.keys()] + [str(id) for id in self.director_panel.checked_params.keys()],
                        'with_origin_country': [str(id) for id in self.country_panel.checked_params.keys()],
                        'release_date.gte': ['-'.join(release_date_gte)],
                        'release_date.lte': ['-'.join(release_date_lte)],
                        'sort_by': [f'{id}.{self.sort_asc_desc.value}' for id in self.sort_panel.checked_params.keys()]}
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
            self.show_msg('По Вашему запросу ничего не было найдено')

    def start_search(self):
        self.search_bttn.setDisabled(True)
        self.search_bttn.setGraphicsEffect(self.disabled_effect)
        QTimer.singleShot(2000, lambda: self.effect_spot.setGraphicsEffect(self.disabled_effect) == self.search_bttn.setDisabled(False))
        
        self.clear_results(self.results.results_layout)
        self.results.results_layout.insertItem(0, QHBoxLayout())
        self.image_queue = deque()
        asyncio.run(self.__search())

    def clear_results(self, widget):
        self.results.current_col_result = 0
        self.results.current_row_result = 0
        self.results.page_num = 1
        self.results.page_cnt = 0
        self.results.film_cnt = 0
        while self.results.count() > 0:
            widget = self.results.widget(0)
            self.results.removeWidget(widget)
            widget.deleteLater()
        self.results.add_page()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.results.results_widget.setFixedWidth(self.results.width()-10)

class ResultsPanel(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.current_col_result = 0
        self.current_row_result = 0
        self.page_cnt = 0
        self.film_cnt = 0
        self.page_num = 1
        self.add_page()

    def add_page(self):
        self.page_cnt += 1
        
        self.results_layout = QVBoxLayout()
        self.results_layout.addLayout(QHBoxLayout())
        self.results_layout.addStretch()

        self.results_widget = QWidget()
        self.results_widget.setLayout(self.results_layout)
        self.results_widget.setFixedWidth(self.width()-10)

        self.cur_page = QScrollArea()
        self.cur_page.setWidgetResizable(True)
        self.cur_page.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.cur_page.setWidget(self.results_widget)

        self.addWidget(self.cur_page)

    def on_scroll(self, value):
        max_value = 960
        if value == 0 and self.page_num > 1:
            self.page_num -= 1
            self.setCurrentIndex(self.page_num-1)
        elif value == max_value and self.page_num < self.page_cnt:
            self.page_num += 1
            self.setCurrentIndex(self.page_num-1)
        print(value, max_value, self.page_num)

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
genres: dict[int, str] = {}
keywords: dict[int, str] = {}
directors: dict[int, str] = {}
actors: dict[int, str] = {}
countries: dict[str, str] = data_provider.get_countries()
# data_provider.get_data(countries)

for param in ('genres', 'keywords', 'directors', 'actors'):
    for row in data_provider.db_request(f'SELECT * FROM {param}'):
        if param in ('genres', 'keywords'):
            locals()[param][row.get('id')] = row.get('name')
        else:
            locals()[param][row.get('id')] = ' '.join([row.get('name'), row.get('surname')])

app = QApplication(sys.argv)
icons = {}
for iconame in ('rating', 'date', 'duration', 'revenue'):
    icons[iconame] = QSvgWidget(f'icons/{iconame}.svg')
    icons[iconame].renderer().setAspectRatioMode(Qt.KeepAspectRatio)

app_window = AppWindow(Поиск = SearchWindow(), Фильм = FilmPage())
app_window.showMaximized()
sys.exit(app.exec_())