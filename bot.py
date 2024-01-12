import logging
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage


host = '-'
port = '-'
user = '-'
password = '-'
database = '-'

API_TOKEN = '-'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

role_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
role_keyboard.add(KeyboardButton('Студент'))
role_keyboard.add(KeyboardButton('Преподаватель'))
role_keyboard.add(KeyboardButton('Администратор'))

logout_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
logout_keyboard.add(KeyboardButton('Выйти из учётной записи'))




class teacherAuthState(StatesGroup):
    logteacher_auth = State()
    passteacher_auth = State()


class studentState(StatesGroup):
    logstudent = State()
    passstudent = State()
    date_input = State()
    logout = State()

class teacherState(StatesGroup):
    logteacher = State()
    passteacher = State()
    date_input_teacher = State()
    add_homework_date = State()
    add_homework_group = State()
    add_homework_task = State()
    logout_teacher = State()
    authentication = teacherAuthState

class teacherAuthenticatedState(StatesGroup):
    view_schedule = State()
    add_homework = State()
    enter_date = State()

class AddHomeworkState(StatesGroup):
    enter_date = State()
    enter_group = State()
    enter_task = State()

# Создаем словарь для хранения данных пользователей
user_data = {}

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот расписания университета. Кто вы?", reply_markup=role_keyboard)
####################################################СТУДЕНТ########################################
@dp.message_handler(lambda message: message.text == "Студент")
async def handle_student_role(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await student(message, chat_id, state)

async def student(message: types.Message, chat_id: int, state: FSMContext):
    await bot.send_message(chat_id, "Введите свой логин:")
    await studentState.logstudent.set()
    await state.update_data(chat_id=chat_id)

@dp.message_handler(state=studentState.logstudent)
async def handle_student_login(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_logstudent = message.text

    # Сохраняем логин в словаре
    user_data[chat_id] = {'p_logstudent': p_logstudent}

    await bot.send_message(chat_id, "Введите свой пароль:")
    await studentState.passstudent.set()

@dp.message_handler(state=studentState.passstudent)
async def handle_student_password(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_password = message.text

    # Сохраняем пароль в словаре
    user_data[chat_id]['p_password'] = p_password

    await bot.send_message(chat_id, "Введите дату в формате ГГГГ-ММ-ДД:")
    await studentState.date_input.set()

@dp.message_handler(state=studentState.date_input)
async def handle_date_input(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    schedule_date_param = message.text

    if schedule_date_param.lower() == 'выйти из учётной записи':
        await handle_logout(message, state)
        return

    await state.update_data(schedule_date_param=schedule_date_param)
    data = await state.get_data()

    try:
        # Получаем логин и пароль из словаря
        p_logstudent = user_data[chat_id]['p_logstudent']
        p_password = user_data[chat_id]['p_password']

        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Вызов функции с логином, паролем и датой
        cursor.execute('SELECT * FROM get_student_schedule(%s, %s, %s)', (p_logstudent, p_password, data['schedule_date_param']))

        # Получаем все результаты функции
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        if results:
            # Группируем результаты по дням
            grouped_results = group_by_date(results)

            # Получаем номер группы из первой строки расписания (если есть)
            group_number = results[0][5] if len(results[0]) > 5 else None
            # Получаем день недели из первой строки расписания (если есть)
            day_of_week = results[0][1] if len(results[0]) > 1 else None

            # Формируем одно сообщение с номером группы и днем недели
            message_text = ""
            if group_number is not None:
                message_text += f"Номер группы: {group_number}\n"
            if day_of_week is not None:
                message_text += f"День недели: {day_of_week}\n"

            # Форматируем расписание и добавляем к сообщению
            for date, data_for_date in grouped_results.items():
                message_text += format_date_schedule(date, data_for_date)

            await bot.send_message(chat_id, message_text, reply_markup=logout_keyboard)

        else:
            await bot.send_message(chat_id, f"На {schedule_date_param} пар нет 😺")

    except Exception as e:
        await bot.send_message(chat_id, f"Неправильный логин, пароль или дата. Попробуйте ещё раз")
        await bot.send_message(chat_id, f"Нажмите /start")
        await state.reset_state()



@dp.message_handler(lambda message: message.text == "Выйти из учётной записи", state=studentState.date_input)
async def handle_logout(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    user_data.pop(chat_id, None)

    await state.finish()
    await message.answer("Вы успешно вышли из учётной записи. Начнем заново.", reply_markup=role_keyboard)

def group_by_date(results):
    """Группирует результаты по дням."""
    grouped_results = {}
    for row in results:
        date = row[0]
        if date not in grouped_results:
            grouped_results[date] = []
        grouped_results[date].append(row[1:])
    return grouped_results

def format_date_schedule(date, schedule):
    """Форматирует расписание для одного дня."""
    if not schedule:
        return f"На {date} расписания нет."

    date_schedule = f"📆Дата: {date}\n"
    for row in schedule:
        date_schedule += "\n"
        date_schedule += "Номер пары: {}\n".format(row[3]) if len(row) > 0 else ""
        date_schedule += "🙀Время начала пары: {}\n".format(row[1]) if len(row) > 1 else ""
        date_schedule += "😸Время окончания пары: {}\n".format(row[2]) if len(row) > 2 else ""
        date_schedule += "Название предмета: {}\n".format(row[5]) if len(row) > 3 else ""
        date_schedule += "😻ФИО преподавателя: {}\n".format(row[6]) if len(row) > 4 else ""
        date_schedule += "Аудитория: {}\n".format(row[7]) if len(row) > 5 else ""
        date_schedule += "😿Домашнее задание: {}\n".format(row[8]) if len(row) > 6 else ""
        date_schedule += "\n"

    return date_schedule



if __name__ == '__main__':
    logging.info("Бот запущен!")
    executor.start_polling(dp, skip_updates=True)