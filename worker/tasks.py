from worker import app
from app.attendance import Attendance
from app.driver import create
from app.supabase import supabase
from enum import Enum
from loguru import logger


class UserStatus(str, Enum):
    # На авторизации
    PENDING = "pending"

    # Успешно авторизован и готов к работе
    READY = "ready"

    # Ошибка авторизации, требуется сменить логин и пароль
    ERROR = "error"


@app.task(time_limit=60 * 2, soft_time_limit=60 * 2)
def login(user_id: str, login: str, password: str):
    logger.info(f"Запуск задачи авторизации для пользователя {user_id}")

    cookies = None
    group = None

    student = supabase.table("students").select("*").eq("user_id", user_id).execute()
    if not student.data:
        supabase.table("students").insert(
            {
                "user_id": user_id,
                "login": login,
                "password": password,
                "status": UserStatus.PENDING.value,
            },
        ).execute()
    else:
        supabase.table("students").update(
            {
                "login": login,
                "password": password,
                "status": UserStatus.PENDING.value,
            },
        ).eq("user_id", user_id).execute()

    for i in range(2):
        driver = create()
        logger.info(f"Создан драйвер для пользователя {user_id}")
        attendance = Attendance(driver=driver)

        try:
            logger.info(f"{i} попытка авторизации для пользователя {user_id}")
            cookies = attendance.login(login, password)
            group = attendance.get_group_name()

            if cookies is not None and group is not None:
                break
        except Exception as e:
            logger.error(f"Ошибка авторизации для пользователя {user_id}: {e}")
            pass
        finally:
            logger.info(f"Закрытие драйвера для пользователя {user_id}")
            driver.quit()

    if cookies is not None and group is not None:
        logger.info(f"Успешная авторизация для пользователя {user_id}")
        supabase.table("students").update(
            {
                "academic_group": group,
                "secrets": cookies,
                "login": login,
                "password": password,
                "status": UserStatus.READY.value,
            },
        ).eq("user_id", user_id).execute()
    else:
        logger.info(f"Ошибка авторизации для пользователя {user_id}")
        supabase.table("students").update(
            {
                "login": login,
                "password": password,
                "status": UserStatus.ERROR.value,
            },
        ).eq("user_id", user_id).execute()
