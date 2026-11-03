# Documind frontend

The web app for Documind, built with Next.js (App Router), TypeScript, Tailwind CSS and TanStack Query. Signed-in users upload PDFs, see how far each one is in processing, and ask questions about a document once it is ready. Answers cite the pages they came from.

The browser never talks to the FastAPI backend directly. It calls this app's own `/api` routes, which forward the request to FastAPI.

## What you can do

- Create an account, sign in and sign out. The session lives in an HttpOnly cookie, so no token is kept in JavaScript or browser storage.
- Upload one PDF at a time. The upload starts as soon as a file is chosen.
- See your documents, newest first, with the number per page adjusted to the available screen height. Each document shows one of three states: Preparing, Ready to ask, or Couldn’t process.
- Delete a document after confirming in a dialog.
- Select a ready document and ask questions. Each answer shows numbered sources that open to the page number and the exact passage.

## Running it locally

Use Node.js 24. The backend and its services must be running first:

- Configure the root `.env` and `backend/.env` as described in the [project README](../README.md).
- Stop any API, dispatcher, and Celery worker processes you previously started manually.
- From the repository root, build and start the backend stack:

```bash
docker compose up -d --build --wait --wait-timeout 180
```

Compose starts PostgreSQL, Redis, and LocalStack, applies database migrations, and starts the API, dispatcher, and Celery worker. The API is available at `http://127.0.0.1:8000`. No separate backend terminals are needed.

To ask questions, the backend also needs `DOCUMIND_OPENAI_API_KEY` and `DOCUMIND_ANSWER_MODEL`.

Then start the frontend from the `frontend` directory:

```bash
cp .env.example .env.local
npm run dev
```

Restart the dev server after changing any setting.

## Configuration

All settings are server-only environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCUMIND_API_URL` | none, required | Address of the FastAPI service. |
| `DOCUMIND_API_TIMEOUT_MS` | `10000` | Time limit for sign-in, document list and delete requests. |
| `DOCUMIND_UPLOAD_TIMEOUT_MS` | `120000` | Time limit for uploads. |
| `DOCUMIND_ANSWER_TIMEOUT_MS` | `100000` | Time limit for answers. Keep it above the backend's embedding and answer timeouts added together. |
| `DOCUMIND_APP_ORIGIN` | request origin in development | Public address of this app. Required in production, including behind a reverse proxy. |
| `DOCUMIND_SESSION_COOKIE_NAME` | `documind_session` | Must match the backend setting. |

## How requests flow

| Browser calls | Forwards to FastAPI |
| --- | --- |
| `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | `/auth/...` |
| `GET /api/documents`, `POST /api/documents` | `/documents` |
| `DELETE /api/documents/{id}` | `/documents/{id}` |
| `POST /api/documents/{id}/answer` | `/documents/{id}/answer` |

- Only the session cookie is forwarded to FastAPI, and cookie attributes from the backend are passed back unchanged.
- Every request that changes something must carry an `Origin` header matching `DOCUMIND_APP_ORIGIN`. Browsers add it automatically, and other clients must send it. Other origins are rejected before they reach FastAPI.
- JSON request bodies are limited to 16 KiB. The backend still enforces its own limits, including the upload size and the PDF check.
- Nothing is retried automatically. An interrupted upload or delete may have succeeded, so the user is asked to check the list first.
- Keep FastAPI on your internal network and expose only this app.

## Behaviour worth knowing

- The document list refreshes every 3 seconds while any document on the page is still preparing, and pauses while the browser tab is hidden.
- Pending questions and their loading state stay with their document when you switch documents. Only one question per document can be in progress at a time.
- Questions are independent. Each document’s questions and answers stay in workspace memory while you switch documents. History is cleared on reload or sign-out, and deleting a document clears its history. History is not saved to browser storage or the backend.
- The answer text from the model contains markers like `[chunk 3]`. The app turns them into numbered source buttons and drops any marker that has no matching source.
- A 401 from any request returns the user to the sign-in screen with a message.

## Project structure

- `src/app`: the page and the `/api` route handlers.
- `src/components`: shared interface pieces, such as the button and the icons.
- `src/features/auth`: sign-in, sign-up and the top bar.
- `src/features/documents`: `api` for requests to the app's routes, `components` for the screens, `hooks` for shared logic and `lib` for plain functions and types.
- `src/lib/server`: helpers used only by the route handlers, such as configuration, origin checks and cookie handling.
- `src/lib/client`: helpers used by the browser code.

## Checks

Run these from the `frontend` directory:

```bash
npm run lint
npm test
npm run typecheck
npm run build
```

Tests use Vitest, React Testing Library and jsdom for components, and plain Node for route handlers and helpers.

Frontend CI runs these checks on pushes and pull requests using Node.js 24 and the committed npm lockfile.
