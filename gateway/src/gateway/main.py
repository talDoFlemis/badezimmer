import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(message)s %(name)s",
    rename_fields={"levelname": "severity", "asctime": "timestamp"},
)
handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

async def discovery_services_job() -> None:
    logger.info("Running startup job: Initializing resources...")
    # Simulate some startup tasks
    await asyncio.sleep(1)
    logger.info("Startup job completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await discovery_services_job()
    yield
    logger.info("Running shutdown job: Cleaning up resources...")
    logger.info("Shutdown job completed.")


from typing import Union


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
