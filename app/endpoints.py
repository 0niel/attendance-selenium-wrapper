from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from app.attendance import Attendance
from app.config import config
from app.supabase import supabase

router = APIRouter()


from worker import app


class Session(BaseModel):
    access_token: str


class Data(BaseModel):
    access_token: str
    login: str
    password: str


class ToApprove(BaseModel):
    user_ids: list[str]
    access_token: str
    token: str


class AcceptInvite(BaseModel):
    invition_key: str
    email: str


@router.post(
    "/login",
)
def login(
    data: Data,
):
    auth_response = supabase.auth.get_user(data.access_token)

    if auth_response.user is None:
        return Response(
            status_code=400,
            content={
                "message": "Сессия не действительна",
            },
        )

    user_id = auth_response.user.id

    app.send_task(
        "worker.tasks.login",
        kwargs={
            "user_id": user_id,
            "login": data.login,
            "password": data.password,
        },
    )
    return Response(status_code=204)


def is_invited_by_admin(user_email: str) -> bool:
    invited_by_admin = (
        supabase.table("invition_logs")
        .select("*")
        .eq("invited_email", user_email)
        .execute()
    )

    if invited_by_admin.data:
        return invited_by_admin.data[0]["user_id"] == config.ADMIN_ID

    return False


@router.post(
    "/approve",
)
def approve(
    data: ToApprove,
):
    auth_response = supabase.auth.get_user(data.access_token)

    if auth_response.user is None:
        return Response(
            status_code=400,
            content={
                "message": "Сессия не действительна",
            },
        )

    u_student = (
        supabase.table("decrypted_students")
        .select("*")
        .eq("user_id", auth_response.user.id)
        .execute()
    )

    if not u_student.data:
        return Response(
            status_code=400,
            content={
                "message": "Пользователь не авторизован",
            },
        )

    academic_group = u_student.data[0].get("academic_group")
    if academic_group is None:
        return Response(
            status_code=400,
            content={
                "message": "Пользователь не авторизован",
            },
        )

    logger.info(
        f"[{academic_group}] Запуск подтрвеждения от имени {auth_response.user.id}"
    )

    students_with_this_group = (
        supabase.table("decrypted_students")
        .select("*")
        .eq("academic_group", academic_group)
        .execute()
    )

    logger.info(
        f"[{academic_group}] Найдено {len(students_with_this_group.data)} студентов: {[student.get('user_id') for student in students_with_this_group.data]}"
    )

    for student in students_with_this_group.data:
        user_id = student.get("user_id")
        secrets = student.get("decrypted_secrets")
        if user_id is None or secrets is None:
            continue

        if user_id not in data.user_ids:
            continue

        if student.get("allow_approve_by_others") == False:
            continue

        attendance = Attendance(cookies=student.get("decrypted_secrets"))
        res = attendance.send_self_approve_request(data.token)
        logger.info(
            f"[{academic_group}] Студент {user_id} отправил запрос на подтверждение. Результат: {res}"
        )


@router.post(
    "/accept-invite",
)
def accept_invite(
    data: AcceptInvite,
):
    logger.info(f"Подтверждение приглашения {data.email}, {data.invition_key}")
    invition_key = (
        supabase.table("invition_keys")
        .select("*")
        .eq("key", data.invition_key)
        .execute()
    )

    if not invition_key.data:
        logger.info("Ключ не действителен")
        return Response(
            status_code=400,
            content={
                "message": "Ключ не действителен",
            },
        )

    user = supabase.auth.admin.get_user_by_id(invition_key.data[0].get("user_id"))
    logger.info(f"Приглашение от пользователя {user.user.email}")
    if not user.user.id == config.ADMIN_ID:
        if not is_invited_by_admin(user.user.email):
            logger.info(
                "Пользователь, который пригласил вас, не обладает правами на это действие"
            )
            return Response(
                status_code=400,
                content={
                    "message": "Пользователь, который пригласил вас, не обладает правами на это действие",
                },
            )

    supabase.auth.admin.invite_user_by_email(data.email)

    supabase.table("invition_logs").insert(
        {
            "user_id": invition_key.data[0].get("user_id"),
            "invited_email": data.email,
        },
    ).execute()

    # Обновляем ключ
    supabase.table("invition_keys").update(
        {"key": str(uuid4()), "updated_at": datetime.now().isoformat()}
    ).eq("user_id", invition_key.data[0].get("user_id")).execute()


@router.post(
    "/get-invition-key",
)
def get_invition_key(
    data: Session,
):
    logger.info("Получение ключа приглашения")
    auth_response = supabase.auth.get_user(data.access_token)
    logger.info("Получена сессия")

    if auth_response.user is None:
        return Response(
            status_code=400,
            content={
                "message": "Сессия не действительна",
            },
        )

    if not auth_response.user.id == config.ADMIN_ID:
        if not is_invited_by_admin(auth_response.user.email):
            return Response(
                status_code=400,
                content={
                    "message": "Вы не обладаете правами на это действие",
                },
            )

    logger.info("Пользователь обладает правами")

    invition_key = (
        supabase.table("invition_keys")
        .select("*")
        .eq("user_id", auth_response.user.id)
        .execute()
    )

    if invition_key.data:
        updated_at = invition_key.data[0].get("updated_at")

        # Если разница во времени больше 12 часов, то обновляем ключ
        if (
            datetime.now() - datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S.%f")
        ).seconds > 43200:
            logger.info(
                f"Обновление ключа. Последнее обновление {updated_at}. Разница: {(datetime.now() - datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%S.%f')).seconds}"
            )
            invition_key = (
                supabase.table("invition_keys")
                .update({"key": str(uuid4()), "updated_at": datetime.now().isoformat()})
                .eq("user_id", auth_response.user.id)
                .execute()
            )
    else:
        invition_key = (
            supabase.table("invition_keys")
            .insert({"user_id": auth_response.user.id, "key": str(uuid4())})
            .execute()
        )

    logger.info("Получен ключ")

    return JSONResponse(
        content={
            "key": invition_key.data[0].get("key"),
        }
    )
