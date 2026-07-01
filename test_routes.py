from fastapi import FastAPI
from app.api.chat_routes import router as chat_router

app = FastAPI()
app.include_router(chat_router, prefix="/api/chat")
for route in app.routes:
    print(route.path, route.methods)
