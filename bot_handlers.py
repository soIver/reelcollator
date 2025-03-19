from data_provider import DataProvider
from bot import bot
from PIL import Image
import io, re

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, BufferedInputFile, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext

import datetime, traceback

PARAMETER_TRANSLATIONS = {
    'name': 'название',
    'director': 'Режиссёр',
    'country': 'Страна',
    'genres': 'Жанры',
    'keywords': 'Ключевые слова',
    'actors': 'Актёры',
    'date': 'Интервал выпуска',
    'sort': 'Сортировка результатов'
}

router = Router()
data_provider = DataProvider()

sort_by: dict[str, str] = {'rating': 'Рейтинг', 'release_date': 'Дата выхода', 'revenue': 'Сумма сборов'}
sort_in: dict[str, str] = {'DESC': 'по убыванию', 'ASC': 'по возрастанию'}

class States(StatesGroup):
    started = State()
    enter_param = State()
    search_params = State()
    enter_title = State()
    enter_interval = State()

async def handle_error(action: Message | CallbackQuery, state: FSMContext):
    user_id = action.from_user.id
    await state.set_state(States.started)
    await send_message(user_id, "Что-то пошло не так. Пожалуйста, повторите попытку позже.")
    print(traceback.format_exc())
                
async def send_message(user_id: int | str, text: str, markup: InlineKeyboardMarkup | ReplyKeyboardMarkup = None, reply_to: int | str = None, document: FSInputFile = None):
    try:
        if not document:
            message = await bot.send_message(user_id, text, reply_markup=markup, reply_to_message_id=reply_to)
        else:
            message = await bot.send_document(user_id, document, caption=text, reply_markup=markup, reply_to_message_id=reply_to)
        return message
    except TelegramForbiddenError:
        pass
    except Exception:
        pass

async def edit_message(message: Message, text: str):
    try:
        if message:
            await message.edit_text(text)
    except Exception:
        pass

async def delete_message(message: Message):
    try:
        if message:
            await message.delete()
    except Exception:
        pass

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
        user_id = message.from_user.id
        if not data_provider.db_request(f'SELECT * FROM users WHERE id = {user_id}'):
            data_provider.db_request(f'INSERT INTO users VALUES ({user_id})')
        data = await state.get_data()
        message_id = data.get('menu_message_id')
        if message_id is None:
            await send_message(user_id, 'Доброго времени суток!')
            message = await send_message(user_id, 'Выберите пункт меню')
            message_id = message.message_id
        await state.update_data(menu_message_id = message_id)
        await set_menu(message_id=message_id, user_id=user_id)

async def set_menu(call: CallbackQuery = None, state: FSMContext = None, message_id: int = None, user_id: int = None):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'🔍 Найти фильм', callback_data='search')],
        [InlineKeyboardButton(text=f'❤️ Список понравившегося', callback_data='favorite')],
        [InlineKeyboardButton(text='📌 Список отложенного', callback_data=f'watchlist')],
        [InlineKeyboardButton(text='🌟 Персональная подборка', callback_data=f'compilation')]
    ])
    if call:
        await delete_message(call.message)
        menu_message_id = await send_message(call.from_user.id, 'Выберите пункт меню', markup)
        await state.update_data(menu_message_id = menu_message_id)
    else:
        try:
            await bot.edit_message_text(
                text='Выберите пункт меню',
                chat_id=user_id,
                message_id=message_id,
                reply_markup=markup
            )
        except TelegramBadRequest:
            pass

@router.callback_query(F.data == 'menu')
async def send_menu_call(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_menu(call, state)

@router.callback_query(F.data == 'search')
async def search(call: CallbackQuery, state: FSMContext):
    try:
        await set_parameters_panel(call, state)
    except Exception:
        await handle_error(call, state)

async def get_current_parameters_text(search_params: dict) -> str:
    text = '\n'
    if search_params.get('name'):
        text += f"🎬 Название: {search_params['name']}\n"
    if search_params.get('director'):
        director_id = next(iter(search_params['director'].keys()))
        director_name = search_params['director'][director_id]
        text += f"🎥 Режиссёр: {director_name}\n"
    if search_params.get('country'):
        country_id = next(iter(search_params['country'].keys()))
        country_name = search_params['country'][country_id]
        text += f"🌍 Страна: {country_name}\n"
    if search_params.get('genres'):
        genre_names = [name for _, name in search_params['genres'].items()]
        text += f"🎭 Жанры: {', '.join(genre_names)}\n"
    if search_params.get('genres-no'):
        genre_names = [name for _, name in search_params['genres-no'].items()]
        text += f"🎭🚫 Нежелательные жанры: {', '.join(genre_names)}\n"
    if search_params.get('keywords'):
        keyword_names = [name for _, name in search_params['keywords'].items()]
        text += f"🔑 Ключевые слова: {', '.join(keyword_names)}\n"
    if search_params.get('keywords-no'):
        keyword_names = [name for _, name in search_params['keywords-no'].items()]
        text += f"🔑🚫 Нежелательные ключевые слова: {', '.join(keyword_names)}\n"
    if search_params.get('actors'):
        actor_names = [name for _, name in search_params['actors'].items()]
        text += f"👤 Актёры: {', '.join(actor_names)}\n"
    if search_params.get('date_gte') and search_params.get('date_lte'):
        text += f"📅 Интервал выхода: {search_params['date_gte']} - {search_params['date_lte']}\n"
    if search_params.get('sort_by'):
        sort_by_value = sort_by.get(search_params['sort_by'], search_params['sort_by'])
        sort_in_value = sort_in.get(search_params.get('sort_in', 'DESC'), 'DESC')
        text += f"🔢 Сортировка: {sort_by_value} ({sort_in_value})\n"
    return text

async def set_parameters_panel(action: CallbackQuery | Message, state: FSMContext):
    data = await state.get_data()
    search_params = data.get('search_params', {})
    current_parameters_text = await get_current_parameters_text(search_params)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Название', callback_data='set_title')],
        [InlineKeyboardButton(text=f'Режиссёр', callback_data='parameter_director')],
        [InlineKeyboardButton(text=f'Страна', callback_data='parameter_country')],
        [InlineKeyboardButton(text='Жанры', callback_data=f'parameter_genres')],
        [InlineKeyboardButton(text=f'Нежелательные жанры', callback_data='parameter_genres-no')],
        [InlineKeyboardButton(text=f'Ключевые слова', callback_data='parameter_keywords')],
        [InlineKeyboardButton(text=f'Нежелательные ключевые слова', callback_data='parameter_keywords-no')],
        [InlineKeyboardButton(text='Актёры', callback_data=f'parameter_actors')],
        [InlineKeyboardButton(text='Интервал выпуска фильма', callback_data=f'set_interval')],
        [InlineKeyboardButton(text='Сортировка результатов', callback_data=f'set_sorting')],
        [InlineKeyboardButton(text='🔍 Начать поиск', callback_data=f'start_search')],
        [InlineKeyboardButton(text='↩️ Вернуться в меню', callback_data=f'menu')]
    ])
    text = f"Выбранные параметры: {current_parameters_text}" if current_parameters_text else "Выберите параметр:"
    if isinstance(action, CallbackQuery):
        await bot.edit_message_text(
            text=text,
            chat_id=action.from_user.id,
            message_id=action.message.message_id,
            reply_markup=markup
        )
    else:
        menu_message_id = data.get('menu_message_id')
        await bot.delete_message(action.from_user.id, menu_message_id)
        message = await send_message(action.from_user.id, text, markup)
        await state.update_data(menu_message_id = message.message_id)

@router.callback_query(F.data == 'set_title')
async def set_title(call: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(States.enter_title)
        await bot.edit_message_text(
            text="Введите название фильма:",
            chat_id=call.from_user.id,
            message_id=call.message.message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='↩️ Вернуться к выбору параметра', callback_data='search')]]
            )
        )
    except Exception:
        await handle_error(call, state)

@router.message(States.enter_title)
async def enter_title_handler(message: Message, state: FSMContext):
    try:
        title = message.text.strip()
        if title:
            await state.update_data(param_type = 'title')
            data = await state.get_data()
            search_params = data.get('search_params', {})
            search_params['name'] = title
            await state.update_data(search_params=search_params)

            await set_parameters_panel(message, state)
    except Exception:
        await handle_error(message, state)

@router.callback_query(F.data == 'set_interval')
async def set_interval(call: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(param_type = 'interval')
        await state.set_state(States.enter_interval)
        await bot.edit_message_text(
            text="Введите интервал выхода фильма в формате:\n\n`ГГГГ.ММ.ДД-ГГГГ.ММ.ДД`\n\nПример: `2000.01.01-2020.12.31`",
            chat_id=call.from_user.id,
            message_id=call.message.message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='↩️ Вернуться к выбору параметра', callback_data='search')]]
            )
        )
    except Exception:
        await handle_error(call, state)

@router.message(States.enter_interval)
async def enter_interval_handler(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        interval = message.text.strip()

        if re.match(r'^\d{4}\.\d{2}\.\d{2}-\d{4}\.\d{2}\.\d{2}$', interval):
            date_gte, date_lte = interval.split('-')
            date_gte = date_gte.replace('.', '-')
            date_lte = date_lte.replace('.', '-')

            data = await state.get_data()
            search_params = data.get('search_params', {})
            search_params['date_gte'] = date_gte
            search_params['date_lte'] = date_lte
            await state.update_data(search_params=search_params)

            await set_parameters_panel(message, state)

        else:
            await send_message(
                user_id,
                "Неправильный формат интервала. Попробуйте снова или вернитесь к выбору параметра.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='↩️ Вернуться к выбору параметра', callback_data='search')]]
                )
            )
    except Exception:
        await handle_error(message, state)

@router.callback_query(F.data.startswith('parameter_'))
async def select_parameter(call: CallbackQuery, state: FSMContext):
    try:
        param_type = call.data.split('_')[1]
        
        await state.update_data(param_type=param_type)
        await state.set_state(States.enter_param)

        await show_parameter_page(call, state)
    except Exception:
        await handle_error(call, state)

async def update_sort_panel_markup(action: Message | CallbackQuery, state: FSMContext) -> InlineKeyboardMarkup:
    user_id = action.from_user.id
    data = await state.get_data()
    sort_in_key = data.get('sort_in_key', 'DESC')
    sort_in_value = sort_in.get(sort_in_key)
    sort_by_key = data.get('sort_by_key', 'rating')
    sort_by_value = sort_by.get(sort_by_key)
    sort_message_id = data.get('sort_message_id')

    sort_by_dict = sort_by.copy()
    sort_by_dict[sort_by_key] = '✅ ' + sort_by_value
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sort_by_dict.get('rating'), callback_data=f'set_sort_by-rating')],
        [InlineKeyboardButton(text=sort_by_dict.get('release_date'), callback_data=f'set_sort_by-release_date')],
        [InlineKeyboardButton(text=sort_by_dict.get('revenue'), callback_data=f'set_sort_by-revenue')],
        [InlineKeyboardButton(text=f'Сортировать: {sort_in_value}', callback_data=f'change_sort_in')],
        [InlineKeyboardButton(text='↩️ Вернуться к выбору параметра', callback_data=f'search')],
    ])
    await bot.edit_message_reply_markup(chat_id=user_id, message_id=sort_message_id, reply_markup=markup)
    return markup

@router.callback_query(F.data.startswith('set_sort_by-'))
async def set_sort_py(call: CallbackQuery, state: FSMContext):
    sort_by_key = call.data.split('-')[1]
    data = await state.get_data()
    search_params = data.get('search_params', {})
    search_params['sort_by'] = sort_by_key
    await state.update_data(search_params=search_params)
    await state.update_data(sort_by_key = sort_by_key)
    await update_sort_panel_markup(call, state)

@router.callback_query(F.data == 'set_sorting')
async def set_sorting(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        user_id = call.from_user.id
        sort_message = await send_message(user_id, f'Установите флажок возле имени параметра, по которому будет производиться сортировка результатов.\nВы также можете изменить порядок сортировки нажатием на соответствующую кнопку.')
        await state.update_data(sort_message_id = sort_message.message_id)
        await update_sort_panel_markup(call, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'change_sort_in')
async def change_sort_in(call: CallbackQuery, state: FSMContext):
    sort_keys = list(sort_in.keys())
    data = await state.get_data()
    sort_in_key = data.get('sort_in_key', 'DESC')
    new_sort_in_key = sort_keys[sort_keys.index(sort_in_key) - 1]
    search_params = data.get('search_params', {})
    search_params['sort_in'] = new_sort_in_key
    await state.update_data(search_params=search_params)
    await state.update_data(sort_in_key = new_sort_in_key)
    await update_sort_panel_markup(call, state)

@router.message(States.enter_param)
async def enter_parameter_value(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        param_type: str = data.get('param_type')
        menu_message_id = data.get('menu_message_id')
        param_value = message.text
        await bot.delete_message(user_id, menu_message_id)
        items = data_provider.get_params_by_page(param_type.split('-')[0], get_all=True)

        exists = param_value in [item.get('name') for item in items]
        if exists:
            item = next(({'id': item['id'], 'name': item['name']} for item in items if item['name'] == param_value), None)
            if item:
                await select_item(param_type, {item['id']: item['name']}, state)
                await show_parameter_page(message, state, param_value)
        else:
            relevant_items = []
            for item in items:
                if param_value.lower() in item['name'].lower():
                    relevant_items.append(item)

            if relevant_items:
                buttons = []
                for item in relevant_items:
                    buttons.append([
                        InlineKeyboardButton(
                            text=item['name'],
                            callback_data=f"select_{param_type}_{item['id']}_{item['name']}"
                        )
                    ])
                buttons.append([InlineKeyboardButton(text='↩️ Вернуться к выбору параметра', callback_data='search')])

                markup = InlineKeyboardMarkup(inline_keyboard=buttons)
                await send_message(
                    user_id,
                    f'Найдены следующие варианты для параметра "{PARAMETER_TRANSLATIONS.get(param_type, param_type)}":',
                    markup
                )
            else:
                await send_message(user_id, "Указанное значение не найдено.")
    except Exception:
        await handle_error(message, state)

@router.callback_query(F.data == 'start_search')
async def start_search(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        user_id = call.from_user.id
        data = await state.get_data()
        search_params = data.get('search_params', {})

        genres_included = list(search_params.get('genres', {}).keys())
        genres_excluded = list(search_params.get('genres-no', {}).keys())
        keywords_included = list(search_params.get('keywords', {}).keys())
        keywords_excluded = list(search_params.get('keywords-no', {}).keys())
        actors = list(search_params.get('actors', {}).keys())
        director_dict = search_params.get('director', {})
        director = next(iter(director_dict.keys()), None) if director_dict else None
        country_dict = search_params.get('country', {})
        country = next(iter(country_dict.keys()), None) if country_dict else None

        movies = data_provider.search_movies(
            genres_included=genres_included,
            genres_excluded=genres_excluded,
            keywords_included=keywords_included,
            keywords_excluded=keywords_excluded,
            actors=actors,
            director=director,
            title_part=search_params.get('name'),
            country=country,
            release_date_gte=search_params.get('date_gte', '1895-12-28'),
            release_date_lte=search_params.get('date_lte', '2026-12-12'),
            order_by=search_params.get('sort_by', 'id'),
            order_dir=search_params.get('sort_in', 'DESC')
        )

        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        data_provider.update_query(
            user_id,
            search_params.get('name', None),
            search_params.get('date_gte', '1895-12-28'),
            search_params.get('date_lte', '2026-12-12'),
            country,
            director,
            current_date,
            actors,
            genres_included,
            genres_excluded,
            keywords_included,
            keywords_excluded
        )

        if movies:
            await state.update_data(movies=movies, current_index=0)
            await show_movie(user_id, state)
        else:
            menu_message_id = data.get(menu_message_id)
            bot.delete_message(user_id, menu_message_id)
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Меню', callback_data=f'menu')]
            ])
            menu_message = await send_message(user_id, "По вашему запросу ничего не было найдено.", markup)
            await state.update_data(menu_message_id = menu_message.message_id)
    except Exception:
        await handle_error(call, state)

async def get_movie_markup(movie_id: int, movie_index: int, movies_len: int, user_id: int, show_details: bool = False):
    is_favorite = data_provider.is_in_list(user_id, movie_id, 'favorite_movies')
    is_watchlist = data_provider.is_in_list(user_id, movie_id, 'watchlist')
    
    inline_keyboard_first = []
    if movie_index > 0:
        inline_keyboard_first.append(InlineKeyboardButton(text='⬅️ Предыдущий', callback_data='prev_movie'))
    if movie_index < movies_len:
        inline_keyboard_first.append(InlineKeyboardButton(text='Следующий ➡️', callback_data='next_movie'))

    markup = InlineKeyboardMarkup(inline_keyboard=[
        inline_keyboard_first,
        [
            InlineKeyboardButton(
                text='❤️ Убрать из понравившегося' if is_favorite else '❤️ Добавить в понравившееся',
                callback_data=f"toggle_favorite_{movie_id}"
            ),
            InlineKeyboardButton(
                text='📌 Убрать из отложенного' if is_watchlist else '📌 Добавить в отложенное',
                callback_data=f"toggle_watchlist_{movie_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text='Скрыть детали' if show_details else '👀 Подробнее',
                callback_data=f"toggle_details_{movie_id}"
            ),
        ],
        [InlineKeyboardButton(text='⭐ Поставить оценку', callback_data=f"rate_movie_{movie_id}")],
        [InlineKeyboardButton(text='↩️ Вернуться в меню', callback_data=f'menu')]
    ])
    return markup
    
async def show_movie(user_id: int, state: FSMContext, show_details: bool = False, update_score: bool = False):
    data = await state.get_data()
    await state.update_data(show_details = show_details)
    movies = data.get('movies', [])
    current_index = data.get('current_index', 0)

    if not movies:
        await bot.send_message(user_id, "Фильмы не найдены.")
        return

    movie: dict = movies[current_index]
    rating = str(movie['rating'] if not update_score else data_provider.get_movie_rating(movie.get('id')))
    score = data_provider.get_movie_score(movie.get('id'), user_id)
    if score:
        rating += f' (ваша оценка: {score})'
    text = (
        f"🎬 <b>{movie['name']}</b>\n"
        f"📅 Дата выхода: {movie['release_date']}\n"
        f"🌍 Страна: {data_provider.get_country_name(movie['release_country'])}\n"
        f"🎥 Режиссёр: {data_provider.get_director_name(movie['director'])}\n"
        f"⭐ Рейтинг: {rating}\n"
        f"📝 Описание: {movie['overview']}"
    )
    
    if show_details:
        text = (
            f"\n👤 Актёры: {', '.join(data_provider.get_actor_names(movie['actors']))}\n"
            f"🎭 Жанры: {', '.join(data_provider.get_genre_names(movie['genres']))}\n"
            f"🔑 Ключевые слова: {', '.join(data_provider.get_keyword_names(movie['keywords']))}\n"
            f"💵 Сумма сборов: {movie['revenue']}\n"
        )

    markup = await get_movie_markup(movie.get('id'), current_index, len(movies) - 1, user_id, show_details)

    movie_photos: list = data.get('movie_photos', [])
    if current_index < len(movie_photos) and movie_photos:
        photo = movie_photos[current_index]
        file_bin = None
    else:
        file_bin = data_provider.get_image_bin(movie.get('poster_link'))
        if file_bin:
            file_bin = await compress_image(file_bin)

    if file_bin:
        photo = BufferedInputFile(file_bin.getvalue(), filename='photo.png')
        movie_photos.append(photo)
        await state.update_data(movie_photos=movie_photos)

    if 'movie_message_id' not in data:
        message = await bot.send_photo(user_id, photo, caption=text, reply_markup=markup)
        await state.update_data(movie_message_id=message.message_id)
    else:
        media = InputMediaPhoto(media=photo, caption=text)
        await bot.edit_message_media(
            chat_id=user_id,
            message_id=data.get('movie_message_id'),
            media=media,
            reply_markup=markup
        )

async def compress_image(byte_arr, quality=50):
    with Image.open(io.BytesIO(byte_arr)) as img:
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=quality)
        img_byte_arr.seek(0)
        return img_byte_arr
    
@router.callback_query(F.data.startswith('rate_movie_'))
async def rate_movie(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[2])
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text='1️⃣', callback_data=f"set_score_{movie_id}_1"),
                InlineKeyboardButton(text='2️⃣', callback_data=f"set_score_{movie_id}_2"),
                InlineKeyboardButton(text='3️⃣', callback_data=f"set_score_{movie_id}_3"),
                InlineKeyboardButton(text='4️⃣', callback_data=f"set_score_{movie_id}_4"),
                InlineKeyboardButton(text='5️⃣', callback_data=f"set_score_{movie_id}_5"),
            ],
            [
                InlineKeyboardButton(text='6️⃣', callback_data=f"set_score_{movie_id}_6"),
                InlineKeyboardButton(text='7️⃣', callback_data=f"set_score_{movie_id}_7"),
                InlineKeyboardButton(text='8️⃣', callback_data=f"set_score_{movie_id}_8"),
                InlineKeyboardButton(text='9️⃣', callback_data=f"set_score_{movie_id}_9"),
                InlineKeyboardButton(text='🔟', callback_data=f"set_score_{movie_id}_10"),
            ]
        ])

        await bot.edit_message_caption(
            caption='Выберите оценку для фильма',
            chat_id=user_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data.startswith('set_score_'))
async def set_score(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[2])
        score = int(call.data.split('_')[3])
        data_provider.set_movie_score(user_id, movie_id, score)
        data = await state.get_data()

        await show_movie(user_id, state, show_details=data.get('show_details', False), update_score=True)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data.startswith('toggle_details_'))
async def toggle_details(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[2])
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        movies = data.get('movies', [])
        current_movie = movies[current_index]

        if current_movie['id'] == movie_id:
            show_details = not data.get('show_details', False)
            await state.update_data(show_details=show_details)
            await show_movie(user_id, state, show_details)
    except Exception:
        await handle_error(call, state)

async def show_parameter_page(action: CallbackQuery | Message, state: FSMContext, last_value: str = None):
    data = await state.get_data()
    param_type = data.get('param_type')
    param_page = data.get('param_page', 0)
    search_params = data.get('search_params', {})
    param_type_common = param_type.split('-')[0]
    param_name = PARAMETER_TRANSLATIONS.get(param_type_common, param_type)
    if len(param_type.split('-')) > 1:
        param_name = "нежелательные " + param_name.lower()

    items = data_provider.get_params_by_page(param_type_common, param_page)

    buttons = []
    for item in items:
        item_id = item['id']
        item_name = item['name']
        is_selected = item_id in search_params.get(param_type, {})
        buttons.append([
            InlineKeyboardButton(
                text=f"{'✅ ' if is_selected else ''}{item_name}",
                callback_data=f"select_{param_type}_{item_id}_{item_name}"
            )
        ])

    navigation_buttons = []
    if param_page > 0:
        navigation_buttons.append(InlineKeyboardButton(text='⬅️ Предыдущая страница', callback_data=f"prev_page_{param_type}"))
    if len(items) == 10:
        navigation_buttons.append(InlineKeyboardButton(text='Следующая страница ➡️', callback_data=f"next_page_{param_type}"))
    buttons.append(navigation_buttons)
    buttons.append([InlineKeyboardButton(text='Завершить выбор', callback_data='finish_selection')])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    if isinstance(action, CallbackQuery):
        await bot.edit_message_text(
            text=f"Выберите варианты из предложенных ниже или введите собственные:",
            chat_id=action.from_user.id,
            message_id=action.message.message_id,
            reply_markup=markup
        )
    else:
        message = await send_message(action.from_user.id, f'Значение "{last_value}" было успешно добавлено!\nВы можете продолжить выбор', markup)
        await state.update_data(menu_message_id=message.message_id)

@router.callback_query(F.data.startswith('select_'))
async def select_item_call(call: CallbackQuery, state: FSMContext):
    try:
        _, param_type, item_id, item_name = call.data.split('_')
        item = {int(item_id): item_name}
        await select_item(param_type, item, state)
        await show_parameter_page(call, state)

    except Exception:
        await handle_error(call, state)

async def select_item(param_type: str, item: dict, state: FSMContext):
    data = await state.get_data()
    search_params = data.get('search_params', {})
    selected_items: dict[str, dict] = search_params.get(param_type, {})

    if param_type in ('director', 'country'):
        search_params[param_type] = item
    else:
        item_id = next(iter(item.keys()))
        if item_id in selected_items:
            del selected_items[item_id]
        else:
            selected_items.update(item)
        search_params[param_type] = selected_items

    await state.update_data(search_params=search_params)

@router.callback_query(F.data.startswith('prev_page_'))
async def prev_page(call: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        param_page = data.get('param_page', 0)
        if param_page > 0:
            param_page -= 1
            await state.update_data(param_page=param_page)
            await show_parameter_page(call, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data.startswith('next_page_'))
async def next_page(call: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        param_page = data.get('param_page', 0)
        param_page += 1
        await state.update_data(param_page=param_page)
        await show_parameter_page(call, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'finish_selection')
async def finish_selection(call: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(States.search_params)
        await set_parameters_panel(call, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data.startswith('toggle_'))
async def toggle_list(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        list_name = call.data.split('_')[1]
        if list_name == 'favorite':
            list_name += '_movies'
        movie_id = int(call.data.split('_')[2])
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        movies = data.get('movies', [])

        if data_provider.is_in_list(user_id, movie_id, list_name):
            data_provider.remove_from_list(user_id, movie_id, list_name)
        else:
            data_provider.add_to_list(user_id, movie_id, list_name)

        markup = await get_movie_markup(movie_id, current_index, len(movies) - 1, user_id)
        await bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'next_movie')
async def next_movie(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        data = await state.get_data()
        movies = data.get('movies', [])
        current_index = data.get('current_index', 0)

        if current_index < len(movies) - 1:
            current_index += 1
            await state.update_data(current_index=current_index)
            await show_movie(user_id, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'prev_movie')
async def prev_movie(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        data = await state.get_data()
        current_index = data.get('current_index', 0)

        if current_index > 0:
            current_index -= 1
            await state.update_data(current_index=current_index)
            await show_movie(user_id, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'favorite')
async def show_favorite_movies(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        user_id = call.from_user.id
        movies = data_provider.get_movies_from_list(user_id, 'favorite_movies')
        if movies:
            await state.update_data(movies=movies, current_index=0)
            await show_movie(user_id, state)
        else:
            await send_message(user_id, "У вас пока нет понравившихся фильмов.")
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'wathclist')
async def show_favorite_movies(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        user_id = call.from_user.id
        movies = data_provider.get_movies_from_list(user_id, 'watchlist')
        if movies:
            await state.update_data(movies=movies, current_index=0)
            await show_movie(user_id, state)
        else:
            await send_message(user_id, "У вас нет фильмов в списке отложенного.")
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'compilation')
async def show_compilation(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        recommended_movies = data_provider.get_personal_recommendations(user_id)
        
        if not recommended_movies:
            await send_message(user_id, "У нас недостаточно данных для формирования персональной подборки. Пожалуйста, оцените несколько фильмов или добавьте их в избранное.")
            return

        await state.update_data(movies=recommended_movies, current_index=0)
        await show_movie(user_id, state)
    except Exception:
        await handle_error(call, state)