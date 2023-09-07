from dotenv import load_dotenv
from dynaconf import LazySettings

load_dotenv(".env")

config = LazySettings(ENVVAR_PREFIX_FOR_DYNACONF=False)
