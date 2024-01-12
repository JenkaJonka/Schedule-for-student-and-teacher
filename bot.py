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
    
#######################################ПРЕПОДАВАТЕЛЬ#################################################################

@dp.message_handler(lambda message: message.text == "Преподаватель")
async def handle_teacher_role(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите свой логин:")
    await teacherAuthState.logteacher_auth.set()
    await state.update_data(chat_id=chat_id)


@dp.message_handler(state=teacherAuthState.logteacher_auth)
async def handle_teacher_login_auth(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_logteacher_auth = message.text

    # Сохраняем логин в словаре user_data
    user_data[chat_id] = {'p_logteacher_auth': p_logteacher_auth}

    await bot.send_message(chat_id, "Введите свой пароль:")
    await teacherAuthState.passteacher_auth.set()

async def authenticate_teacher(chat_id):
    try:
        p_logteacher_auth = user_data[chat_id]['p_logteacher_auth']
        p_password_auth = user_data[chat_id]['p_password_auth']

        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Проверяем, существует ли пользователь с указанными учетными данными и ролью 'Преподаватель'
        cursor.execute('SELECT * FROM Пользователь WHERE Логин = %s AND Пароль = %s AND Роль = %s', (p_logteacher_auth, p_password_auth, 'преподаватель'))

        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return result is not None

    except Exception as e:
        print(e)
        return False

@dp.message_handler(state=teacherAuthState.passteacher_auth)
async def handle_teacher_password_auth(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_password_auth = message.text

    # Сохраняем пароль в словаре user_data
    user_data[chat_id]['p_password_auth'] = p_password_auth

    # Аутентификация преподавателя
    if await authenticate_teacher(chat_id):
        await bot.send_message(chat_id, "Авторизация успешна!")

        # Добавляем кнопки после успешной аутентификации
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton('Посмотреть расписание'))
        keyboard.add(KeyboardButton('Добавить домашнее задание'))
        keyboard.add(KeyboardButton('Выйти из учётной записи'))

        await bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

        await teacherAuthenticatedState.view_schedule.set()
    else:
        await bot.send_message(chat_id, "Неверный логин или пароль. Попробуйте ещё раз.")
        await state.finish()

@dp.message_handler(lambda message: message.text == "Посмотреть расписание", state=teacherAuthenticatedState.view_schedule)
async def handle_view_schedule(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите дату в формате ГГГГ-ММ-ДД:")
    await teacherAuthenticatedState.enter_date.set()

@dp.message_handler(state=teacherAuthenticatedState.enter_date)
async def handle_teacher_enter_date(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    schedule_date_param = message.text

    try:
        # Получаем логин и пароль из словаря user_data
        p_logteacher_auth = user_data[chat_id]['p_logteacher_auth']
        p_password_auth = user_data[chat_id]['p_password_auth']

        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Вызов функции с логином, паролем и введенной датой
        cursor.execute('SELECT * FROM get_teacher_schedule(%s, %s, %s)', (p_logteacher_auth, p_password_auth, schedule_date_param))

        # Получаем все результаты функции
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        if results:
            grouped_results = group_by_date(results)

            # Выводим дату и день недели
            message_text = f"Ваше расписание на {schedule_date_param}:\n\n"
            day_of_week = results[0][1] if len(results[0]) > 1 else None
            if day_of_week is not None:
                message_text += f"День недели: {day_of_week}\n"

            # Форматируем расписание и добавляем к сообщению
            for date, data_for_date in grouped_results.items():
                message_text += f"\n📆Дата: {date}\n"

                # Сортируем данные по номеру пары перед выводом
                sorted_data_for_date = sorted(data_for_date, key=lambda x: x[3])

                for row in sorted_data_for_date:
                    message_text += "Номер пары: {}\n".format(row[3]) if len(row) > 0 else ""
                    message_text += "🙀Время начала пары: {}\n".format(row[1]) if len(row) > 1 else ""
                    message_text += "😸Время окончания: {}\n".format(row[2]) if len(row) > 2 else ""
                    message_text += "Номер группы: {}\n".format(row[4]) if len(row) > 3 else ""
                    message_text += "Название предмета: {}\n".format(row[5]) if len(row) > 4 else ""
                    message_text += "Номер аудитории: {}\n".format(row[7]) if len(row) > 5 else ""
                    message_text += "😻Домашнее задание: {}\n".format(row[8]) if len(row) > 6 else ""
                    message_text += "\n"

            await bot.send_message(chat_id, message_text, reply_markup=logout_keyboard)

        else:
            await bot.send_message(chat_id, f"На {schedule_date_param} у вас нет занятий 😺")

    except Exception as e:
        await bot.send_message(chat_id, "Произошла ошибка при получении расписания. Попробуйте ещё раз. Нажмите /start")
        await state.finish()

@dp.message_handler(lambda message: message.text == "Добавить домашнее задание", state=teacherAuthenticatedState.view_schedule)
async def handle_add_homework(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите дату в формате ГГГГ-ММ-ДД:")
    await AddHomeworkState.enter_date.set()

@dp.message_handler(state=AddHomeworkState.enter_date)
async def handle_enter_date_for_homework(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    date_input = message.text

    await state.update_data(date_input=date_input)
    await bot.send_message(chat_id, "Введите номер группы:")
    await AddHomeworkState.enter_group.set()

@dp.message_handler(state=AddHomeworkState.enter_group)
async def handle_enter_group_for_homework(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    group_number = message.text

    await state.update_data(group_number=group_number)
    await bot.send_message(chat_id, "Введите текст домашнего задания:")
    await AddHomeworkState.enter_task.set()

@dp.message_handler(state=AddHomeworkState.enter_task)
async def handle_enter_task_for_homework(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    task_text = message.text

    data = await state.get_data()
    date_input = data['date_input']
    group_number = data['group_number']

    # Вызов процедуры в базе данных для добавления домашнего задания
    try:
        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()
        cursor.execute('CALL add_homework(%s, %s, %s, %s, %s)', (user_data[chat_id]['p_logteacher_auth'], user_data[chat_id]['p_password_auth'], data['date_input'], data['group_number'], task_text))
        conn.commit()
        cursor.close()
        conn.close()

        await bot.send_message(chat_id, "Домашнее задание успешно добавлено! Нажмите /start")

    except Exception as e:
        await bot.send_message(chat_id, "Произошла ошибка при добавлении домашнего задания. Попробуйте ещё раз.")
        print(e)

    finally:
        await state.finish()

@dp.message_handler(lambda message: message.text == "Выйти из учётной записи", state=teacherAuthenticatedState.view_schedule)
async def handle_logout_teacher(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    # Remove user data for the current chat_id
    user_data.pop(chat_id, None)

    await state.finish()  # Finish the current state
    await message.answer("Вы успешно вышли из учётной записи. Начнем заново.", reply_markup=role_keyboard)

if __name__ == '__main__':
    logging.info("Бот запущен!")
    executor.start_polling(dp, skip_updates=True)
