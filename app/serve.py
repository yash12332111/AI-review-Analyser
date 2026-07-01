import os
import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # $PORT is injected by Render; --port flag is kept for local convenience
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()
    
    print(f"Starting server on port {args.port}...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=args.port, reload=False)
