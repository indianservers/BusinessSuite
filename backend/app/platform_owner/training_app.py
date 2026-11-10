"""Local platform portal API, independent of customer schema startup.

Run: python -m uvicorn app.platform_owner.training_app:app --host 127.0.0.1 --port 1535
The complete owner portal is available; role permissions still apply server-side.
"""
from fastapi import FastAPI, Depends, Request
import app.db.base  # Register ORM relationships used by shared platform services.
from app.platform_owner.auth import PlatformLogin, login
from app.platform_owner.session import get_platform_db
from app.platform_owner.api import router

app=FastAPI(title='Indian Servers · Local Platform Owner Portal')
app.include_router(router,prefix='/api/v1')


@app.post('/api/v1/auth/platform/login')
def sign_in(data:PlatformLogin,request:Request,db=Depends(get_platform_db)):
    return login(data,request,db)
