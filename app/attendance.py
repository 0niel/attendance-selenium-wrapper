import re
import time
from webbrowser import Chrome

import httpx
import requests
from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

RE_GROUP_NAME = re.compile(r"[А-Я]{4}-\d{2}-\d{2}")

LOGIN_URL = "https://attendance.mirea.ru/api/login?redirectUri=https%3A%2F%2Fattendance-app.mirea.ru"


from enum import IntEnum


class NotYetApprovedReason(IntEnum):
    NOT_YET_APPROVED_REASON_UNKNOWN = 0
    NOT_YET_APPROVED_REASON_INCORRECT_TOKEN = 1
    NOT_YET_APPROVED_REASON_WAITING = 2
    NOT_YET_APPROVED_REASON_NO_LINK_TO_LESSON = 3


class Attendance:
    def __init__(self, driver: Chrome | None = None, cookies: str | None = None):
        self.driver = driver
        self.cookies = cookies

    def __send_login_credentials(self, email: str, password: str):
        login_input = WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located((By.XPATH, "//input[@name='login']"))
        )
        password_input = WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located((By.XPATH, "//input[@name='password']"))
        )
        submit_login_input = WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located((By.XPATH, "//input[@value='Войти']"))
        )

        login_input.clear()
        password_input.clear()

        login_input.send_keys(email)
        password_input.send_keys(password)

        submit_login_input.click()

    def __send_submit_button(self):
        submit_button = WebDriverWait(self.driver, 10).until(
            ec.visibility_of_element_located((By.XPATH, "//input[@value='Разрешить']"))
        )
        submit_button.click()

    def login(self, email: str, password: str) -> str | None:
        if self.driver is None:
            raise Exception("Драйвер не инициализирован")

        logger.info("Открытие страницы авторизации")
        self.driver.get(LOGIN_URL)
        logger.info("Страница авторизации открыта")
        self.__send_login_credentials(email, password)
        logger.info("Отправлены данные авторизации")

        self.__send_submit_button()
        logger.info("Отправлена кнопка разрешения")
        redirected = WebDriverWait(self.driver, 10).until(
            ec.url_contains("https://attendance-app.mirea.ru")
        )

        if redirected:
            logger.info("Получение cookies")
            self.driver.get("https://attendance-app.mirea.ru/visiting-logs")

            requested_urls = [request.url for request in self.driver.requests]

            headers = None
            while not any("GetMeInfo" in url for url in requested_urls):
                requested_urls = [request.url for request in self.driver.requests]

            for request in self.driver.requests:
                if "GetMeInfo" in request.url:
                    headers = request.headers
                    break

            cookies = headers.get("Cookie")
            self.cookies = cookies

            return cookies

        return None

    def __encode_empty_grpc_payload(self, payload: bytes):
        payload = payload.encode("utf-8")
        return b"\x00" + len(payload).to_bytes(4, byteorder="big") + payload

    def __encode_self_approve_grpc_payload(self, token):
        # b'\x00\x00\x00\x00&\n$' + токен
        payload = token.encode("utf-8")
        return b"\x00\x00\x00\x00&\n$" + payload

    def __get_request_headers(self):
        return {
            "Content-Type": "application/grpc-web",
            "Cookie": self.cookies,
            "X-User-Agent": "grpc-web-javascript/0.1",
            "X-Grpc-Web": "1",
        }

    def get_group_name(self) -> str or None:
        if self.cookies is None:
            raise Exception("Cookies не инициализированы")

        response = requests.post(
            "https://attendance.mirea.ru/rtu_tc.rtu_attend.app.ElderService/GetAvailableVisitingLogs",
            headers=self.__get_request_headers(),
            data=self.__encode_empty_grpc_payload(""),
        )

        data = response.text

        match = RE_GROUP_NAME.search(data)
        return match.group(0) if match else None

    def send_self_approve_request(self, token: str):
        if self.cookies is None:
            raise Exception("Cookies не инициализированы")

        response = requests.post(
            "https://attendance.mirea.ru/rtu_tc.rtu_attend.app.StudentService/SelfApproveAttendance",
            headers=self.__get_request_headers(),
            data=self.__encode_self_approve_grpc_payload(token),
        )

        data = response.content

        return self.__get_not_yet_status(data)

    def __get_not_yet_status(self, data: bytes):
        # 8-й байт - статус
        return NotYetApprovedReason(data[8])
