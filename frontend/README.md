# Orbit frontend

React + Vite. The original UI is preserved in `prototype.html`.

From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open [localhost:5173](http://localhost:5173). API requests are proxied to FastAPI on port 8000; start the backend in a separate terminal.

```powershell
npm.cmd run build
```

Restart FastAPI after building to serve the app at [127.0.0.1:8000](http://127.0.0.1:8000).

See the [project README](../README.md) for virtual environment setup, configuration, validation, and troubleshooting.
