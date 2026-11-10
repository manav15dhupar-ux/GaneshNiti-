// API base URL.
//  ""  (default)  -> same origin: the FastAPI server also serves this frontend (Render/Docker/local uvicorn).
//  "https://your-api.onrender.com" -> use this ONLY if the frontend is hosted elsewhere (e.g. GitHub Pages);
//  then set ALLOWED_ORIGINS on the backend to that site's origin.
window.GANESHNITI_API_BASE = "";
