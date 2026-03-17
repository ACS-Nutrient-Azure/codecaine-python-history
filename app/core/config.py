from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "History Service"
    app_env: str = "development"
    app_port: int = 8000

    # DB 개별 변수 (ECS 환경변수로 주입)
    db_user: str = ""
    db_password: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""

    # 로컬 개발용 직접 URL (설정 시 개별 변수보다 우선)
    database_url: str = ""

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Cognito
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    aws_region: str = "ap-northeast-2"

    # JWT fallback (dev only — used when cognito_user_pool_id is not set)
    jwt_secret_key: str = "dev-secret-key"
    jwt_algorithm: str = "HS256"

    allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174"

    @property
    def origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
