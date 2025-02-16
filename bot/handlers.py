from data_provider import DataProvider
from bot.bot import bot

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, BufferedInputFile, LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

router = Router()
db = DataProvider

class States(StatesGroup):
    enter_param = State()

async def handle_error(action: Message | CallbackQuery, state: FSMContext):
    user_id = action.from_user.id
    await state.set_state(States.started)
    markup = await get_default_markup(user_id)
    await send_message(user_id, "Что-то пошло не так. Пожалуйста, повторите попытку позже.", markup=markup)

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
    try:
        user_id = message.from_user.id
        if not await db.db_request(f'SELECT * FROM users WHERE id = {user_id}'):
            await db.db_request(f'INSERT INTO users VALUES ({user_id})')

        markup = await get_default_markup(user_id)
        await send_message(user_id, 'Доброго времени суток!', markup)
    except Exception:
        await handle_error(message, state)

async def get_default_markup():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Найти фильм', callback_data='search')],
        [InlineKeyboardButton(text=f'Получить персональную подборку', callback_data='personal')],
        [InlineKeyboardButton(text=f'Список понравившегося', callback_data='set_parameter_needin_png')],
        [InlineKeyboardButton(text='Список отложенного', callback_data=f'slice_flowchart')],
    ])
    return markup

@router.callback_query(F.data == 'search')
async def search(call: CallbackQuery, state: FSMContext):
    try:
        user_id = call.from_user.id
        data = await state.get_data()
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
        [InlineKeyboardButton(text='Вернуться в меню', callback_data=f'menu')],

    ])
        await send_message(user_id, 'Вы ещё не выбрали ни одного параметра', markup)
        await send_message(user_id, 'Выберите параметр из приведённых ниже 👇', markup)
    except Exception:
        await handle_error(call, state)
