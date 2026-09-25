# Orbit frontend

React + Vite. The original UI is preserved in `prototype.html`.

## Routes

The public landing page is served at [localhost:5173](http://localhost:5173/).
After authentication, the application uses `/chat`, `/dashboard`, `/coding`, and
`/practice`. The local preloaded demo is available at `/demo`; `start.bat` opens
that route directly, while visiting `/` lets you review the landing page first.

From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open [localhost:5173](http://localhost:5173/). API requests are proxied to FastAPI on port 8000; start the backend in a separate terminal.

```powershell
npm.cmd run build
```

Restart FastAPI after building to serve the app at [127.0.0.1:8000](http://127.0.0.1:8000/). The FastAPI fallback also serves `/demo`, `/chat`, `/dashboard`, `/coding`, and `/practice`.

See the [getting-started guide](../GET_STARTED.md) for virtual environment setup, configuration, validation, and troubleshooting.
