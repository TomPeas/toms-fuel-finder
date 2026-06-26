from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gov_client_id: str
    gov_client_secret: str
    gov_base_url: str


settings = Settings()
