import sys, asyncio, json
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import QSvgWidget
from data_provider import DataProvider
from collections import deque, Counter
from datetime import date
from functools import partial

class ImageLoader(QRunnable):
    def __init__(self, movie_id, poster_link, callback: QObject):
        super().__init__()
        self.poster_link = poster_link
        self.movie_id = movie_id
        self.callback = callback
    
    def run(self):
        image_data = data_provider.get_image_bin(self.poster_link)
        pixmap = self.__pixmap_from_bytes(image_data)
        QMetaObject.invokeMethod(self.callback, "add_film_card", Qt.QueuedConnection, Q_ARG(int, self.movie_id), Q_ARG(QPixmap, pixmap))

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
        self.setMaximumSize(600, 800)
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
    
    def updateBorders(self, enabled):
        color_text = '#000'
        color_bg = '#f5f5f5'
        borders = '4px solid #4d8458' if enabled else 'none'
        self.setStyleSheet(f'''
            QLabel {{
            background-color: {color_bg};
            color: {color_text};
            font-size: 15pt;
            font-family: Calibri;
            font-weight: bold;
            border-left: {borders};
        }}''')

class ParameterPanel(QWidget):
    def __init__(self, name: str, placeholder: str, default: str, values: dict[str | int, str], one_value: bool):
        super().__init__()
        self.checked_params: dict[int, list[int, int]] = {}
        self.current_row, self.current_col = 0, 0
        self.values = values
        self.one_value = one_value
        param_label = QLabel(name)
        self.completer = QCompleter([value for value in values.values()])
        self.completer.setCompletionMode(QCompleter.InlineCompletion)
        self.param_edit = QLineEdit(default)
        self.param_edit.setMaximumWidth(300)
        self.param_edit.setPlaceholderText(placeholder)
        self.param_edit.setCompleter(self.completer)
        self.param_edit.setObjectName('param-edit')
        self.main_lo = QVBoxLayout()
        child_lo = QHBoxLayout()
        self.completer.activated.connect(lambda: self.__update_checked_params(self.param_edit.text()))
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
                    new_label.setObjectName('param')

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
    def __init__(self, movie_data: dict[str] = {}, poster: QPixmap = None):
        super().__init__()
        self.fid = movie_data.get('id', '')
        self.poster_img = poster
        self.title_txt = movie_data.get('name', '')
        self.description_txt = movie_data.get('overview', '')
        self.rating_txt = str(movie_data.get('rating', 0))
        self.poster_path = movie_data.get('poster_link', '')
        self.release_date = str(movie_data.get('release_date', ''))
        self.revenue_txt = str(movie_data.get('revenue', 0))
        self.runtime = str(movie_data.get('runtime', 0))
        self.release_country = movie_data.get('origin_country', '')
        self.__init_ui()

    def __init_ui(self):
        self.poster = ScaledLabel()
        if self.poster_img:
            self.poster.setPixmap(self.poster_img)
            self.poster.setAlignment(Qt.AlignCenter)
            
        self.poster_link = QLineEdit(self.poster_path)
        self.rating = QLabel(text=self.rating_txt)
        self.rating.sizeHint = lambda: QSize(50, 60)
        self.date = QLineEdit(self.release_date)
        self.date.sizeHint = lambda: QSize(200, 60)
        self.duration = QLineEdit(str(self.runtime))
        self.duration.sizeHint = lambda: QSize(150, 60)
        self.revenue = QLineEdit(str(self.revenue_txt))
        self.revenue.sizeHint = lambda: QSize(150, 60)
        self.create_btn = CustomPushButton('Создать новую карточку фильма')
        self.create_btn.setEnabled(False)
        self.create_btn.updateBackgroundColor()
        self.delete_btn = CustomPushButton('Удалить')
        self.delete_btn.setEnabled(False)
        self.delete_btn.updateBackgroundColor()
        self.save_btn = CustomPushButton('Сохранить')

        self.title = QLineEdit(self.title_txt)
        self.title.setObjectName('title-edit')
        self.description = QPlainTextEdit(self.description_txt)
        country_param = ParameterPanel('Страна:', '', countries.get(self.release_country), countries, True)
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

        botside_l = QHBoxLayout()
        botside_l.addWidget(icons['rating'])
        botside_l.addWidget(self.rating)
        botside_l.addWidget(icons['revenue'])
        botside_l.addWidget(self.revenue)
        botside_l.addWidget(icons['date'])
        botside_l.addWidget(self.date)
        botside_l.addWidget(icons['duration'])
        botside_l.addWidget(self.duration)

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

class FilmCard(QWidget):
    def __init__(self, movie_data: dict[str], poster: QPixmap):
        super().__init__()
        self.movie_data = movie_data
        self.poster = poster
        self.poster_copy = poster
        self.title = movie_data.get('name')
        self.rating = movie_data.get('rating')
        self.__init_ui()

    def __init_ui(self):
        layout = QVBoxLayout(self)

        self.poster_obj = ScaledLabel()
        self.poster_obj.setMaximumSize(600, 500)
        self.poster_obj.setPixmap(self.poster)
        self.poster_obj.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if len(self.title) > 16:
            title_label = f'{self.title[:16]}...'
        else:
            title_label = self.title
        self.title_obj = QLabel(text=title_label)
        self.title_obj.setStyleSheet('font-size: 18pt')
        self.title_obj.setWordWrap(True)

        if self.rating > 0:
            font_size = 18
            text = str(self.rating)
        else:
            font_size = 12
            text = 'нет\nоценок'
        self.rating_obj = QLabel(text=text)
        bg_color = f'rgb({255 - int(self.rating)*20}, {int(self.rating)*20}, 0)' if self.rating > 0 else 'gray'
        self.rating_obj.setStyleSheet(f'font-size: {font_size}pt; padding-left: 5px; padding-right: 5px; border: 2px solid #555; background-color: {bg_color}; border-radius: 5px; color: #fff')
        self.rating_obj.setMaximumSize(100, 60)

        layout.addWidget(self.poster_obj)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.title_obj, stretch=1)
        h_layout.addWidget(self.rating_obj)

        layout.addLayout(h_layout)

        self.poster_obj.setMouseTracking(True)
        self.poster_obj.setCursor(Qt.PointingHandCursor)
        self.poster_obj.installEventFilter(self)

    def __open_film_page(self):
        app_window.main_window.removeTab(1)
        app_window.main_window.insertTab(1, FilmPage(self.movie_data,
                                            poster = self.poster_copy), 'Фильм')
        app_window.main_window.setCurrentIndex(1)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Enter and source is self.poster_obj:
            self.poster_obj.updateBorders(True)
        elif event.type() == QEvent.Leave and source is self.poster_obj:
            self.poster_obj.updateBorders(False)
        elif event.type() == QEvent.MouseButtonPress and source is self.poster_obj:
            self.__open_film_page()
        return super().eventFilter(source, event)

    def delete(self):
        self.title_obj.deleteLater()
        self.rating_obj.deleteLater()
        self.poster_obj.deleteLater()
        self.layout().deleteLater()
        self.deleteLater()

class ButtonsPanel(QWidget):
    def __init__(self, external_method, *buttons: dict[str, str]):
        super().__init__()
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        self.external_method = external_method
        self.buttons: list[dict[str, CustomPushButton]] = list(buttons)

        for i, btn in enumerate(self.buttons):
            self.buttons[i]['obj'] = CustomPushButton(btn.get('name'))
            self.buttons[i].get('obj').setCursor(Qt.PointingHandCursor)
            self.buttons[i].get('obj').clicked.connect(partial(self.__change_value, i))
            main_layout.addWidget(self.buttons[i].get('obj'))

        self.value = buttons[0].get('value')
        self.buttons[0].get('obj').setEnabled(False)
        self.buttons[0].get('obj').updateBackgroundColor()

    def __change_value(self, btn_index: int):
        btn = self.buttons[btn_index]
        self.value = btn.get('value')
        for i, btn in enumerate(self.buttons):
            enabled = False if i == btn_index else True
            self.buttons[i].get('obj').setEnabled(enabled)
            self.buttons[i].get('obj').updateBackgroundColor()
        if self.external_method is not None:
            self.external_method()
            
class CustomPushButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

    def updateBackgroundColor(self):
        enabled = self.isEnabled()
        color_text_light = '#303030'
        color_setting = ' #7d7d7d'
        color_btn = ' #4d8458' if enabled else color_setting
        color_btn_hover = ' #6ba476'
        self.setStyleSheet(f'''QPushButton {{
            font-size: 16pt;
            font-family: Calibri;
            background-color: {color_btn};
            color: {color_text_light};
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
        }}
        QPushButton:hover {{
            background-color: {color_btn_hover};
        }}''')

class SearchPage(QWidget):
    def __init__(self):
        super().__init__()
        self.sort_params = {'rating': 'рейтингу',
                            'release_date': 'дате выхода',
                            'revenue': 'сумме сборов'}
        self.__initUI()

    def __initUI(self):
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите название фильма')
        self.search_edit.setMinimumHeight(60)

        self.search_bttn = CustomPushButton('Поиск')
        self.search_bttn.setMinimumHeight(60)
        self.search_bttn.clicked.connect(self.start_search)
        self.search_bttn.setCursor(Qt.PointingHandCursor)

        sort_label = QLabel('Сортировать результаты по')
        self.sort_panel = ParameterPanel('', '', '', self.sort_params, True)
        self.sort_panel.setMinimumWidth(250)
        self.sort_panel.setObjectName('param-edit')
        self.sort_asc_desc = ButtonsPanel(None, {'name': '↑', 'value': 'DESC'}, {'name': '↓', 'value': 'ASC'})

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
        self.show_msg('')

        main_layout = QHBoxLayout()
        main_layout.addLayout(self.v_layout)
        main_layout.addWidget(self.results)
        
        main_layout.setStretch(0, 2)
        main_layout.setStretch(1, 3)
        self.setLayout(main_layout)

    @pyqtSlot(int, QPixmap)
    def add_film_card(self, movie_id: int, pixmap: QPixmap):
        if not pixmap.isNull():
            result = FilmCard(self.movies.get(movie_id), pixmap)
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

            movie_id, poster_link = self.image_queue.popleft()
            loader = ImageLoader(movie_id, poster_link, self)
            QThreadPool.globalInstance().start(loader)
            self.results.film_cnt += 1
    
    def show_msg(self, msg: str):
        msg_label = QLabel(msg)
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.setObjectName('param-label')
        self.results.addWidget(msg_label)
        self.results.setCurrentIndex(1)

    async def __search(self):
        release_date_gte, release_date_lte = self.date_edit.text().split('-')
        release_date_gte, release_date_lte = release_date_gte.split('.'), release_date_lte.split('.')
        release_date_gte.reverse()
        release_date_lte.reverse()
        if int(''.join(release_date_gte)) > int(''.join(release_date_lte)):
            self.show_msg('Первая дата интервала выхода фильма не может быть больше второй')

        movies = data_provider.search_movies(
            genres_included=[str(id) for id in self.genres_panel.checked_params.keys()],
            genres_excluded=[str(id) for id in self.genres_panel_no.checked_params.keys()],
            keywords_included=[str(id) for id in self.keywords_panel.checked_params.keys()],
            keywords_excluded=[str(id) for id in self.keywords_panel_no.checked_params.keys()],
            actors=[str(id) for id in self.actors_panel.checked_params.keys()],
            director=[str(id) for id in self.director_panel.checked_params.keys()],
            title_part=self.search_edit.text(),
            country=[str(id) for id in self.country_panel.checked_params.keys()],
            release_date_gte='-'.join(release_date_gte),
            release_date_lte='-'.join(release_date_lte),
            order_by=[str(id) for id in self.sort_panel.checked_params.keys()],
            order_dir=self.sort_asc_desc.value
        )
        self.movies = {}
        if movies:
            for movie in movies:
                movie_id = movie.get('id')
                movie_poster = movie.get('poster_link')
                self.movies[movie_id] = movie
                self.image_queue.append((movie_id, movie_poster))
            self.process_next_image()
        else: 
            self.show_msg('По Вашему запросу ничего не было найдено')

    def start_search(self):
        self.search_bttn.setEnabled(False)
        self.search_bttn.updateBackgroundColor()
        QTimer.singleShot(2500, lambda: self.search_bttn.setEnabled(True))
        QTimer.singleShot(2501, lambda: self.search_bttn.updateBackgroundColor())

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
        self.results_widget.setFixedHeight(1923)

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

class StatsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.__init_ui()
        self.__update_data()
    
    def __init_ui(self):
        top_lo = QHBoxLayout()
        self.usr_cnt_value = QLabel()
        self.update_bttn = QPushButton('Обновить данные')
        self.update_bttn.clicked.connect(self.__update_data)
        self.update_bttn.setCursor(Qt.PointingHandCursor)
        top_lo.addWidget(QLabel('Количество пользователей в системе:'))
        top_lo.addWidget(self.usr_cnt_value)
        top_lo.addStretch()
        top_lo.addWidget(self.update_bttn, alignment=Qt.AlignRight)
        
        self.film_bttns = ButtonsPanel(self.set_data, {'name': 'общее', 'value': 'all'}, {'name': 'среднее', 'value': 'avg'})
        films_top_lo = QHBoxLayout()
        films_top_lo.addWidget(self.film_bttns)
        films_top_lo.addWidget(QLabel('количество фильмов'))

        self.favorite_value = QLabel()
        favorite_lo = QVBoxLayout()
        favorite_lo.addWidget(QLabel('добавленных в понравившееся'))
        favorite_lo.addWidget(self.favorite_value)
        favorite_widget = QWidget()
        favorite_widget.setObjectName('stats')
        favorite_widget.setLayout(favorite_lo)

        self.watchlist_value = QLabel()
        watchlist_lo = QVBoxLayout()
        watchlist_lo.addWidget(QLabel('добавленных в отложенное'))
        watchlist_lo.addWidget(self.watchlist_value)
        watchlist_widget = QWidget()
        watchlist_widget.setObjectName('stats')
        watchlist_widget.setLayout(watchlist_lo)

        films_lo = QVBoxLayout()
        films_lo.addLayout(films_top_lo)
        films_lo.addWidget(favorite_widget)
        films_lo.addWidget(watchlist_widget)
        films_widget = QWidget()
        films_widget.setObjectName('stats')
        films_widget.setLayout(films_lo)

        self.query_bttns = ButtonsPanel(self.set_data, {'name': 'общее', 'value': 'all'}, {'name': 'среднее', 'value': 'avg'})
        query_top_lo = QHBoxLayout()
        query_top_lo.addWidget(self.query_bttns)
        query_top_lo.addWidget(QLabel('количество запросов'))

        self.query_month_value = QLabel()
        query_month_lo = QVBoxLayout()
        query_month_lo.addWidget(QLabel('месяц'))
        query_month_lo.addWidget(self.query_month_value)
        query_month_widget = QWidget()
        query_month_widget.setObjectName('stats')
        query_month_widget.setLayout(query_month_lo)

        self.query_week_value = QLabel()
        query_week_lo = QVBoxLayout()
        query_week_lo.addWidget(QLabel('неделя'))
        query_week_lo.addWidget(self.query_week_value)
        query_week_widget = QWidget()
        query_week_widget.setObjectName('stats')
        query_week_widget.setLayout(query_week_lo)

        self.query_day_value = QLabel()
        query_day_lo = QVBoxLayout()
        query_day_lo.addWidget(QLabel('день'))
        query_day_lo.addWidget(self.query_day_value)
        query_day_widget = QWidget()
        query_day_widget.setObjectName('stats')
        query_day_widget.setLayout(query_day_lo)

        query_bot_lo = QHBoxLayout()
        query_bot_lo.addWidget(query_month_widget)
        query_bot_lo.addWidget(query_week_widget)
        query_bot_lo.addWidget(query_day_widget)

        queries_lo = QVBoxLayout()
        queries_lo.addLayout(query_top_lo)
        queries_lo.addLayout(query_bot_lo)
        queries_widget = QWidget()
        queries_widget.setObjectName('stats')
        queries_widget.setLayout(queries_lo)

        bot_left_lo = QVBoxLayout()
        bot_left_lo.addWidget(films_widget)
        bot_left_lo.addWidget(queries_widget)

        self.users_genres_value = QLabel()
        users_genres_lo = QVBoxLayout()
        users_genres_lo.addWidget(QLabel('Жанры'))
        users_genres_lo.addWidget(self.users_genres_value)

        self.users_keywords_value = QLabel()
        users_keywords_lo = QVBoxLayout()
        users_keywords_lo.addWidget(QLabel('Ключевые слова'))
        users_keywords_lo.addWidget(self.users_keywords_value)

        self.users_directors_value = QLabel()
        users_directors_lo = QVBoxLayout()
        users_directors_lo.addWidget(QLabel('Режиссёры'))
        users_directors_lo.addWidget(self.users_directors_value)

        self.users_actors_value = QLabel()
        users_actors_lo = QVBoxLayout()
        users_actors_lo.addWidget(QLabel('Актёры'))
        users_actors_lo.addWidget(self.users_actors_value)

        users_genres_widget = QWidget()
        users_genres_widget.setObjectName('stats')
        users_genres_widget.setLayout(users_genres_lo)
        users_keywords_widget = QWidget()
        users_keywords_widget.setObjectName('stats')
        users_keywords_widget.setLayout(users_keywords_lo)
        users_directors_widget = QWidget()
        users_directors_widget.setObjectName('stats')
        users_directors_widget.setLayout(users_directors_lo)
        users_actors_widget = QWidget()
        users_actors_widget.setObjectName('stats')
        users_actors_widget.setLayout(users_actors_lo)

        users_lo = QGridLayout()
        users_lo.addWidget(users_genres_widget, 0, 0)
        users_lo.addWidget(users_keywords_widget, 0, 1)
        users_lo.addWidget(users_directors_widget, 1, 0)
        users_lo.addWidget(users_actors_widget, 1, 1)

        users_widget = QWidget()
        users_widget.setObjectName('stats')
        users_widget.setLayout(users_lo)
        self.user_bttns = ButtonsPanel(self.set_data, {'name': 'месяц', 'value': 'month'}, {'name': 'неделю', 'value': 'week'}, {'name': 'день', 'value': 'day'})

        users_filter_lo = QHBoxLayout()
        users_filter_lo.addWidget(QLabel('запросов за'))
        users_filter_lo.itemAt(users_filter_lo.count()-1).widget().setObjectName('stats')
        users_filter_lo.addWidget(self.user_bttns)

        bot_right_lo = QVBoxLayout()
        bot_right_lo.addWidget(QLabel('Пользовательские предпочтения на основе'), alignment=Qt.AlignTop)
        bot_right_lo.itemAt(bot_right_lo.count()-1).widget().setObjectName('stats')
        bot_right_lo.addLayout(users_filter_lo)
        bot_right_lo.addWidget(users_widget, alignment=Qt.AlignTop)

        bot_lo = QHBoxLayout()
        bot_lo.addLayout(bot_left_lo)
        bot_lo.addLayout(bot_right_lo)

        main_lo = QVBoxLayout()
        main_lo.addLayout(top_lo)
        main_lo.addLayout(bot_lo)
        self.setLayout(main_lo)

    def __update_data(self):
        data = data_provider.get_stats()
        self.usr_cnt = data.get('usr_cnt', 0)
        self.favorite = data.get('favorite', 0)
        self.watchlist = data.get('watchlist', 0)
        self.query_day = data.get('query_day', 0)
        self.query_week = data.get('query_week', 0)
        self.query_month = data.get('query_month', 0)
        self.user_queries_day = data.get('user_queries_day', {})
        self.user_queries_week = data.get('user_queries_week', {})
        self.user_queries_month = data.get('user_queries_month', {})
        self.set_data()

    def set_data(self):
        self.usr_cnt_value.setText(str(self.usr_cnt))
        if self.usr_cnt == 0:
            self.usr_cnt = 1
        match self.film_bttns.value:
            case 'all':
                self.favorite_value.setText(str(self.favorite))
                self.watchlist_value.setText(str(self.watchlist))
            case 'avg':
                self.favorite_value.setText(str(self.favorite // self.usr_cnt))
                self.watchlist_value.setText(str(self.watchlist // self.usr_cnt))
        match self.query_bttns.value:
            case 'all':
                self.query_day_value.setText(str(self.query_day))
                self.query_week_value.setText(str(self.query_week))
                self.query_month_value.setText(str(self.query_month))
            case 'avg':
                self.query_day_value.setText(str(self.query_day // self.usr_cnt))
                self.query_week_value.setText(str(self.query_week // self.usr_cnt))
                self.query_month_value.setText(str(self.query_month // self.usr_cnt))
        match self.user_bttns.value:
            case 'month':
                user_queries = self.user_queries_month
            case 'week':
                user_queries = self.user_queries_week
            case 'day':
                user_queries = self.user_queries_day

        most_common_params = {}
        for param in ((self.users_genres_value, 'genres'), (self.users_keywords_value, 'keywords'), 
                      (self.users_actors_value, 'actors'), (self.users_directors_value, 'directors')):
            counter = Counter(user_queries.get(param[1]))
            most_common_three = counter.most_common(3)
            most_common_params[param[1]] = [item[0] for item in most_common_three]
            if not most_common_params[param[1]]:
                res = 'нет информации'
            else:
                res = ', '.join(most_common_params[param[1]])
            param[0].setText(res)

class MainWindow(QTabWidget):
    def __init__(self, **tabs):
        super().__init__()
        
        self.__init_ui()
        for key, value in tabs.items():
          self.addTab(value, str(key))
    
    def __init_ui(self):
        color_edit = '#eaeaea'
        color_edit_hover = '#78938a'
        color_text = '#000'
        color_text_light = '#303030'
        color_bg = '#f5f5f5'
        color_bg_light = ' #fff'
        color_border = ' #1b1b1b'
        color_setting = ' #7d7d7d'
        color_setting_hover = ' #6e6e6e'
        color_btn = ' #4d8458'
        color_btn_hover = ' #6ba476'
        color_deletion = ' #d62828'
        self.setStyleSheet(f'''
        QTabBar::tab {{
            background-color: {color_edit};
            color: {color_text};
            border: 1px solid {color_border};
            font-family: Calibri;
            font-size: 15pt;
            border-radius: 5%;
            margin: 10%;
            height: 50px;
            width: 200%
        }}
        QTabBar::tab:selected {{
            margin-top: 15%;
            background-color: {color_bg_light};
        }}
        QTabBar::tab:hover {{
            background-color: {color_edit_hover};
        }}
        QTabBar::tab:selected:hover {{
            margin-top: 15%;
            background-color: {color_bg_light};
        }}
        QWidget {{
            background-color: {color_bg};
            border: none;
        }}
        QWidget#stats {{
            background-color: {color_edit};
            border: none;
            border: 1px solid {color_border};
            border-radius: 5%;
        }}
        QScrollArea {{
            font-size: 15pt;
            font-weight: bold;
            background-color: {color_edit};
            border: 1px solid {color_border};
        }}
        QPlainTextEdit {{
            font-size: 13pt;
            font-weight: bold;
            background-color: {color_edit};
            border: 1px solid {color_border};
            border-radius: 5%;
        }}
        QLabel {{
            background-color: {color_bg};
            color: {color_text};
            font-size: 15pt;
            font-family: Calibri;
            font-weight: bold;
        }}
        QLabel#stats {{
            background-color: {color_bg};
            color: {color_text_light};
            font-size: 18pt;
            font-family: Calibri;
            font-weight: bold;
            border: none;
        }}
        QLabel#param {{
            font-size: 13pt;
            font-family: Calibri;
            font-weight: bold;
        }}
        QLabel#param-label {{
            font-size: 15pt;
            font-weight: bold;
            background-color: {color_edit};
            border: 1px solid {color_border};
        }}
        QLineEdit {{
            color: {color_text};
            font-size: 16pt;
            font-family: Calibri;
            background-color: {color_edit};
            border: 1px solid {color_border};
            border-radius: 5%;
            padding: 5px;
        }}
        QLineEdit#param-edit {{
            font-size: 15pt;
            font-weight: bold;
            background-color: {color_edit};
            border: none;
        }}
        QLineEdit#title-edit {{
            font-size: 24pt;
            font-weight: bold;
            background-color: {color_edit};
            border: 1px solid {color_border};
            border-radius: 5%;
        }}
        QPushButton {{
            font-size: 16pt;
            font-family: Calibri;
            background-color: {color_btn};
            color: {color_text_light};
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
        }}
        QPushButton:hover {{
            background-color: {color_btn_hover};
        }}
        QPushButton#settings {{
            background-color: {color_setting};
        }}
        QPushButton#settings:hover {{
            background-color: {color_setting_hover};
        }}
        QPushButton#deletion {{
            background-color: {color_setting};
            color: #000;
            border-radius: 20px;
            padding: 0;
            font-size: 20pt;
            font-weight: bold
        }}
        QPushButton#deletion:hover {{
            background-color: {color_deletion};
            color: {color_edit}
        }}
        QCompleter {{
            color: {color_text};
            background-color: {color_setting_hover};
        }}
        ''')

class AppWindow(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWindowTitle("Reelcollator")
        self.setMinimumSize(720, 480)
        self.main_window = MainWindow(Поиск = SearchPage(), Фильм = FilmPage(), Статистика = StatsPage())
        scene = QGraphicsScene()
        self.awidth = QDesktopWidget().width() - 20
        self.aheight = QDesktopWidget().height() - 130
        self.aspect_ratio = self.awidth / self.aheight
        self.is_fullscreen = False
        scene_widget = scene.addWidget(self.main_window)
        scene_widget.setGeometry(QRectF(0, 0, self.awidth, self.aheight))
        self.setScene(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

        new_size = event.size()
        expected_height = int(new_size.width() / self.aspect_ratio)
        if new_size.height() != expected_height:
            self.setFixedHeight(expected_height)

        self.fitInView(QRectF(0, 0, 1900, 1050), Qt.AspectRatioMode.KeepAspectRatio)

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange:
            if self.windowState() & Qt.WindowFullScreen:
                self.is_fullscreen = True
            else:
                self.is_fullscreen = False
                self.setFixedHeight(int(self.width() / self.aspect_ratio))

        super().changeEvent(event)

data_provider = DataProvider()
genres: dict[int, str] = {}
keywords: dict[int, str] = {}
directors: dict[int, str] = {}
actors: dict[int, str] = {}
countries: dict[str, str] = {}

data_free = False
if not data_free:
    countries: dict[str, str] = data_provider.get_countries()
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

app_window = AppWindow()
app_window.showMaximized()
sys.exit(app.exec_())