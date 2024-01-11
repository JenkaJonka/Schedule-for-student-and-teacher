import logging
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage


host = 'localhost'
port = '5432'
user = 'postgres'
password = '123'
database = 'raspisanie'

API_TOKEN = '6558178432:AAHagj_sq34NbKggzuvOkj6JiV5PTKLX2Zc'

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
###################АДМИНИСТРАТОР###############################################################################
class AddUserState(StatesGroup):
    enter_login = State()
    enter_password = State()
    enter_role = State()

class AdminState(StatesGroup):
    logadmin = State()
    passadmin = State()
    date_input_admin = State()
    start_admin = State()
    add_user = State()
    add_student = State()
    add_teacher = State()

class AddStudentState(StatesGroup):
    enter_user_id = State()
    enter_student_name = State()
    enter_group_number = State()

class AddTeacherState(StatesGroup):
    enter_user_id = State()
    enter_teacher_name = State()
    enter_teacher_email = State()
    

@dp.message_handler(lambda message: message.text == "Администратор")
async def handle_admin_role(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await admin_authentication(message, chat_id, state)

async def admin_authentication(message: types.Message, chat_id: int, state: FSMContext):
    await bot.send_message(chat_id, "Введите свой логин:")
    await AdminState.logadmin.set()
    await state.update_data(chat_id=chat_id)

@dp.message_handler(state=AdminState.logadmin)
async def handle_admin_login(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_logadmin = message.text

    # Сохраняем логин в словаре
    user_data[chat_id] = {'p_logadmin': p_logadmin}

    await bot.send_message(chat_id, "Введите свой пароль:")
    await AdminState.passadmin.set()

@dp.message_handler(state=AdminState.passadmin)
async def handle_admin_password(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    p_passadmin = message.text

    # Сохраняем пароль в словаре
    user_data[chat_id]['p_passadmin'] = p_passadmin

    try:
        # Получаем логин и пароль из словаря
        p_logadmin = user_data[chat_id]['p_logadmin']
        p_passadmin = user_data[chat_id]['p_passadmin']

        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Проверяем логин, пароль и роль админа в таблице "Пользователь"
        cursor.execute('SELECT Роль FROM "Пользователь" WHERE "Логин" = %s AND "Пароль" = %s', (p_logadmin, p_passadmin))
        role = cursor.fetchone()

        if role and role[0] == 'админ':
            await AdminState.start_admin.set()  # Перемещаем эту строку выше
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("Добавить пользователя"))
            keyboard.add(KeyboardButton("Добавить студента"))
            keyboard.add(KeyboardButton("Добавить преподавателя"))
            await bot.send_message(chat_id, "Вы успешно вошли как администратор.", reply_markup=keyboard)
        else:
            await bot.send_message(chat_id, "Неправильный логин, пароль или вы не администратор.")
            await state.reset_state()

    except Exception as e:
        await bot.send_message(chat_id, f"Произошла ошибка при аутентификации администратора. Попробуйте еще раз.")
        await state.reset_state()

    finally:
        cursor.close()
        conn.close()

@dp.message_handler(lambda message: message.text == "Добавить пользователя", state=AdminState.start_admin)
async def add_user_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите логин нового пользователя:")
    await AddUserState.enter_login.set()

@dp.message_handler(state=AddUserState.enter_login)
async def enter_login_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    new_user_login = message.text
    await state.update_data(new_user_login=new_user_login)
    await bot.send_message(chat_id, "Введите пароль нового пользователя:")
    await AddUserState.enter_password.set()

@dp.message_handler(state=AddUserState.enter_password)
async def enter_password_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    new_user_password = message.text
    await state.update_data(new_user_password=new_user_password)
    await bot.send_message(chat_id, "Введите роль нового пользователя:")
    await AddUserState.enter_role.set()

@dp.message_handler(state=AddUserState.enter_role)
async def enter_role_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    new_user_role = message.text
    await state.update_data(new_user_role=new_user_role)

    user_data = await state.get_data()
    new_user_login = user_data.get("new_user_login")
    new_user_password = user_data.get("new_user_password")
    new_user_role = user_data.get("new_user_role")

    try:
        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        cursor.execute(f'INSERT INTO "Пользователь" ("Логин", "Пароль", "Роль") VALUES (%s, %s, %s) RETURNING "ID_пользователя"', (new_user_login, new_user_password, new_user_role))
        new_user_id = cursor.fetchone()[0]
        conn.commit()

        await bot.send_message(chat_id, f"Пользователь с ID {new_user_id}, логином {new_user_login} успешно добавлен с ролью {new_user_role}.")
        await state.reset_state()
    finally:
        cursor.close()
        conn.close()

# Добавьте обработчик для кнопки "Добавить студента"
@dp.message_handler(lambda message: message.text == "Добавить студента")
async def add_student_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите ID пользователя студента:")
    await AddStudentState.enter_user_id.set()

@dp.message_handler(state=AddStudentState.enter_user_id)
async def enter_user_id_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.text
    await state.update_data(user_id=user_id)
    await bot.send_message(chat_id, "Введите ФИО студента:")
    await AddStudentState.enter_student_name.set()

# Обработчик для ввода ФИО студента
@dp.message_handler(state=AddStudentState.enter_student_name)
async def enter_student_name_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    student_name = message.text
    await state.update_data(student_name=student_name)
    await bot.send_message(chat_id, "Введите номер группы:")
    await AddStudentState.enter_group_number.set()

# Обработчик для ввода номера группы студента
@dp.message_handler(state=AddStudentState.enter_group_number)
async def enter_group_number_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    group_number = message.text

    # Достаем данные из состояния
    user_data = await state.get_data()
    user_id = user_data.get("user_id")
    student_name = user_data.get("student_name")
    try:
        # Создаем подключение к базе данных
        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Вставляем данные студента в таблицу "Студент"
        insert_student_query = '''
            INSERT INTO "Студент" ("ID_пользователя", "ФИО_студента", "Номер_группы")
            VALUES (%s, %s, %s);
        '''
        cursor.execute(insert_student_query, (user_id, student_name, group_number))
        conn.commit()

        await bot.send_message(chat_id, f"Студент {student_name} успешно добавлен в группу {group_number}.")
        await state.reset_state()
        
    except Exception as e:
        await bot.send_message(chat_id, f"Произошла ошибка при добавлении студента: {str(e)}. Попробуйте еще раз.")
        await state.reset_state()


    finally:
        cursor.close()
        conn.close()

@dp.message_handler(lambda message: message.text == "Добавить преподавателя")
async def add_teacher_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Введите ID пользователя:")
    await AddTeacherState.enter_user_id.set()

# Обработчик для ввода ID пользователя
@dp.message_handler(state=AddTeacherState.enter_user_id)
async def enter_user_id_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.text
    await state.update_data(user_id=user_id)
    await bot.send_message(chat_id, "Введите ФИО преподавателя:")
    await AddTeacherState.enter_teacher_name.set()

# Обработчик для ввода ФИО преподавателя
@dp.message_handler(state=AddTeacherState.enter_teacher_name)
async def enter_teacher_name_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    teacher_name = message.text
    await state.update_data(teacher_name=teacher_name)
    await bot.send_message(chat_id, "Введите почту преподавателя:")
    await AddTeacherState.enter_teacher_email.set()

# Обработчик для ввода почты преподавателя
@dp.message_handler(state=AddTeacherState.enter_teacher_email)
async def enter_teacher_email_handler(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    teacher_email = message.text

    # Достаем данные из состояния
    user_data = await state.get_data()
    user_id = user_data.get("user_id")
    teacher_name = user_data.get("teacher_name")

    try:
        # Создаем подключение к базе данных
        conn = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        # Вставляем данные преподавателя в таблицу "Преподаватель"
        cursor.execute(
            'INSERT INTO "Преподаватель" ("ID_пользователя", "ФИО_преподавателя", "Почта") VALUES (%s, %s, %s)',
            (user_id, teacher_name, teacher_email)
        )
        conn.commit()

        await bot.send_message(chat_id, f"Преподаватель {teacher_name} успешно добавлен с почтой {teacher_email}.")
        await state.reset_state()

    except Exception as e:
        await bot.send_message(chat_id, f"Произошла ошибка при добавлении преподавателя: {str(e)}. Попробуйте еще раз.")
        await state.reset_state()

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    logging.info("Бот запущен!")
    executor.start_polling(dp, skip_updates=True)