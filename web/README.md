# InterFrames Studio

The React/TypeScript interface for the local InterFrames API.

```powershell
npm install
npm run dev
```

By default Vite proxies `/api/v1` and `/health` to `http://localhost:8000`. Set `VITE_API_PROXY` for a different development API, or `VITE_API_URL` in the build environment for a hosted API origin. The production API must configure CORS for the web origin.

Routes: `/studio`, `/studio/:id`, and `/history`.
