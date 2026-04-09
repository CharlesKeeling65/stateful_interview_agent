import uvicorn

from app.core.config import settings
from app.main import app


def main() -> None:
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
    )


if __name__ == "__main__":
    main()
