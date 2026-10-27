import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=1534,
        reload=True,
        log_level="info",
        proxy_headers=False,  # The application validates configured proxy CIDRs itself.
    )
