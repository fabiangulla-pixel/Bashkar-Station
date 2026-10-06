"""python -m api  →  http://localhost:8422/docs"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", 8422)))
