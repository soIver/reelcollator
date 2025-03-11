from data_provider import DataProvider
from bot import bot
from PIL import Image
import io

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, BufferedInputFile, InputMediaPhoto
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext

import datetime, traceback

PARAMETER_TRANSLATIONS = {
    'name': 'Название',
    'director': 'Режиссёр',
    'country': 'Страна',
    'genres': 'Жанры',
    'notgenres': 'Нежелательные жанры',
    'kwords': 'Ключевые слова',
    'notkwords': 'Нежелательные ключевые слова',
    'actors': 'Актёры',
    'date': 'Дата выпуска фильма',
    'sort': 'Сортировка результатов'
}

router = Router()
data_provider = DataProvider()

genres: dict[int, str] = {}
keywords: dict[int, str] = {}
directors: dict[int, str] = {}
actors: dict[int, str] = {}
countries: dict[str, str] = {}
sort_by: dict[str, str] = {'rating': 'Рейтинг', 'release_date': 'Дата выхода', 'revenue': 'Сумма сборов'}
sort_in: dict[str, str] = {'DESC': 'по убыванию', 'ASC': 'по возрастанию'}

countries: dict[str, str] = data_provider.get_countries()
for param in ('genres', 'keywords', 'directors', 'actors'):
    for row in data_provider.db_request(f'SELECT * FROM {param}'):
        if param in ('genres', 'keywords'):
            locals()[param][row.get('id')] = row.get('name')
        else:
            locals()[param][row.get('id')] = ' '.join([row.get('name'), row.get('surname')])

class States(StatesGroup):
    started = State()
    enter_param = State()
    search_params = State()

async def handle_error(action: Message | CallbackQuery, state: FSMContext):
    user_id = action.from_user.id
    await state.set_state(States.started)
    await send_message(user_id, "Что-то пошло не так. Пожалуйста, повторите попытку позже.")
    print(traceback.format_exc())

async def delete_inline(message: Message):
    if message and message.reply_markup:
        new_markup = InlineKeyboardMarkup(inline_keyboard=[])
        if message.reply_markup != new_markup:
            try:
                await message.edit_reply_markup(reply_markup=new_markup)
            except TelegramBadRequest as e:
                if "Bad Request: message is not modified" in e.message:
                    pass
                else:
                    raise e
                
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

        await send_message(user_id, 'Доброго времени суток!')
        await send_menu(user_id)

async def send_menu(user_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Найти фильм', callback_data='search')],
        [InlineKeyboardButton(text=f'Список понравившегося', callback_data='favorite')],
        [InlineKeyboardButton(text='Список отложенного', callback_data=f'watchlist')],
    ])
    await send_message(user_id, 'Выберите пункт меню 👇', markup)

@router.callback_query(F.data == 'menu')
async def send_menu_call(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await delete_message(call.message)
    await send_menu(call.from_user.id)

@router.callback_query(F.data == 'search')
async def search(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        await send_parameters_panel(call, state)
    except Exception:
        await handle_error(call, state)

async def send_parameters_panel(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    markup = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=f'Название', callback_data='parameter_name')],
    [InlineKeyboardButton(text=f'Режиссёр', callback_data='parameter_director')],
    [InlineKeyboardButton(text=f'Страна', callback_data='parameter_country')],
    [InlineKeyboardButton(text='Жанры', callback_data=f'parameter_genres')],
    [InlineKeyboardButton(text=f'Нежелательные жанры', callback_data='parameter_notgenres')],
    [InlineKeyboardButton(text=f'Ключевые слова', callback_data='parameter_kwords')],
    [InlineKeyboardButton(text=f'Нежелательные ключевые слова', callback_data='parameter_notkwords')],
    [InlineKeyboardButton(text='Актёры', callback_data=f'parameter_actors')],
    [InlineKeyboardButton(text='Дата выпуска фильма', callback_data=f'parameter_date')],
    [InlineKeyboardButton(text='Сортировка результатов', callback_data=f'set_sorting')],
    [InlineKeyboardButton(text='Вернуться в меню', callback_data=f'menu')],
])
    await send_message(user_id, 'Выберите параметр из приведённых ниже 👇', markup)

@router.callback_query(F.data.startswith('parameter_'))
async def select_parameter(call: CallbackQuery, state: FSMContext):
    await delete_message(call.message)
    try:
        user_id = call.from_user.id
        param_type = call.data.split('_')[1]
        
        await state.update_data(param_type=param_type)
        await state.set_state(States.enter_param)

        param_name = PARAMETER_TRANSLATIONS.get(param_type, param_type)
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Вернуться к выбору параметра', callback_data=f'search')],
        ])
        await send_message(user_id, f'Введите значение для параметра "{param_name}" или выберите один из предложенных:', markup)
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
    sort_by_dict[sort_by_key] = sort_by_value + ' ✅'
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sort_by_dict.get('rating'), callback_data=f'set_sort_by-rating')],
        [InlineKeyboardButton(text=sort_by_dict.get('release_date'), callback_data=f'set_sort_by-release_date')],
        [InlineKeyboardButton(text=sort_by_dict.get('revenue'), callback_data=f'set_sort_by-revenue')],
        [InlineKeyboardButton(text=f'Сортировать: {sort_in_value}', callback_data=f'change_sort_in')],
        [InlineKeyboardButton(text='Вернуться к выбору параметра', callback_data=f'search')],
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
    await delete_inline(call.message)
    try:
        user_id = call.from_user.id
        sort_message = await send_message(user_id, f'Установите флажок возле имени параметра, по которому будет производиться сортировка результатов.\nВы также можете изменить порядок сортировки нажатием на соответствующую кнопку.')
        await state.update_data(sort_message_id = sort_message.message_id)
        await update_sort_panel_markup(call, state)
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data == 'change_sort_in')
async def select_parameter(call: CallbackQuery, state: FSMContext):
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
        param_type = data.get('param_type')
        param_value = message.text

        search_params = data.get('search_params', {})
        search_params[param_type] = param_value
        await state.update_data(search_params=search_params)

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Добавить ещё параметр', callback_data='search')],
            [InlineKeyboardButton(text='Начать поиск', callback_data='start_search')],
        ])
        param_name = PARAMETER_TRANSLATIONS.get(param_type, param_type)
        await send_message(user_id, f"Параметр '{param_name}' сохранён. Хотите добавить ещё параметр или начать поиск?", markup)
    except Exception:
        await handle_error(message, state)

@router.callback_query(F.data == 'start_search')
async def start_search(call: CallbackQuery, state: FSMContext):
    await delete_inline(call.message)
    try:
        user_id = call.from_user.id
        data = await state.get_data()
        search_params = data.get('search_params', {})

        movies = data_provider.search_movies(
            genres_included=search_params.get('genres'),
            genres_excluded=search_params.get('notgenres'),
            keywords_included=search_params.get('kwords'),
            keywords_excluded=search_params.get('notkwords'),
            actors=search_params.get('actors'),
            director=search_params.get('director'),
            title_part=search_params.get('name'),
            country=search_params.get('country'),
            release_date_gte=search_params.get('date_gte'),
            release_date_lte=search_params.get('date_lte'),
            order_by=search_params.get('sort_by'),
            order_dir=search_params.get('sort_in')
        )
        
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        data_provider.update_query(user_id, search_params.get('name', None), search_params.get('date_gte', '1895-12-28'), search_params.get('date_lte', '2026-12-12'), search_params.get('country', None), search_params.get('director', None), current_date, search_params.get('actors', []), search_params.get('genres', []), search_params.get('notkwords', []))
        if movies:
            await state.update_data(movies=movies, current_index=0)
            await show_movie(user_id, state)
        else:
            await send_message(user_id, "По вашему запросу ничего не найдено.")
    except Exception:
        await handle_error(call, state)

async def get_movie_markup(movie_id: int, movie_index: int, movies_len: int, user_id: int):
    is_favorite = data_provider.is_favorite(user_id, movie_id)
    is_watchlist = data_provider.is_watchlist(user_id, movie_id)

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
        [InlineKeyboardButton(text='Подробнее', callback_data=f"movie_{movie_id}")]
    ])
    return markup
    
async def show_movie(user_id: int, state: FSMContext):
    data = await state.get_data()
    movies = data.get('movies', [])
    current_index = data.get('current_index', 0)

    if not movies:
        await bot.send_message(user_id, "Фильмы не найдены.")
        return

    movie: dict = movies[current_index]
    text = (
        f"🎬 <b>{movie['name']}</b>\n"
        f"📅 Дата выхода: {movie['release_date']}\n"
        f"🌍 Страна: {movie['release_country']}\n"
        f"⭐ Рейтинг: {movie['rating']}\n"
        f"📝 Описание: {movie['overview']}"
    )
    markup = await get_movie_markup(movie.get('id'), current_index, len(movies) - 1, user_id)

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
        await state.update_data(movie_photos = movie_photos)

    if 'movie_message_id' not in data:
        message = await bot.send_photo(user_id, photo, caption=text, reply_markup=markup)
        await state.update_data(movie_message_id=message.message_id)
    else:
        media = InputMediaPhoto(media=photo, caption=text)
        await bot.edit_message_media(
            chat_id=user_id,
            message_id=data['movie_message_id'],
            media=media,
            reply_markup=markup
        )

async def compress_image(byte_arr, quality=50):
    with Image.open(io.BytesIO(byte_arr)) as img:
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=quality)
        img_byte_arr.seek(0)
        return img_byte_arr
    
@router.callback_query(F.data.startswith('toggle_favorite_'))
async def toggle_favorite(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[2])
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        movies = data.get('movies', [])

        if data_provider.is_favorite(user_id, movie_id):
            data_provider.remove_favorite(user_id, movie_id)
        else:
            data_provider.add_favorite(user_id, movie_id)

        markup = await get_movie_markup(movie_id, current_index, len(movies) - 1, user_id)
        await bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=data['movie_message_id'],
            reply_markup=markup
        )
    except Exception:
        await handle_error(call, state)

@router.callback_query(F.data.startswith('toggle_watchlist_'))
async def toggle_watchlist(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[2])
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        movies = data.get('movies', [])

        if data_provider.is_watchlist(user_id, movie_id):
            data_provider.remove_watchlist(user_id, movie_id)
        else:
            data_provider.add_watchlist(user_id, movie_id)

        markup = await get_movie_markup(movie_id, current_index, len(movies) - 1, user_id)
        await bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=data['movie_message_id'],
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