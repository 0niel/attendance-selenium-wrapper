from webbrowser import Chrome

from fake_useragent import UserAgent
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from app.config import config


def create() -> Chrome:
    caps = DesiredCapabilities().CHROME

    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--proxy-server=worker:8087")
    opt = {
        "request_storage": "memory",
        "auto_config": False,
        "addr": "0.0.0.0",
        "port": 8087,
    }

    ua = UserAgent()
    user_agent = ua.random

    options.add_argument(f"user-agent={user_agent}")

    return webdriver.Remote(
        config.SELENIUM_URL,
        desired_capabilities=caps,
        options=options,
        seleniumwire_options=opt,
    )
