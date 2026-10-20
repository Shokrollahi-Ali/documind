This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## Document uploads

The homepage lets you select, replace, remove, and upload one PDF. It displays the saved document metadata after a successful upload. The Saved documents list loads persisted metadata from FastAPI, newest first, with ten documents per page. It remains available after a reload and refreshes after successful uploads. TanStack Query manages the list cache; the file selection stays in local React state.

Copy `.env.example` to `.env.local` in the frontend directory, then set `DOCUMIND_API_URL` to your FastAPI service URL. This variable is server-only. `DOCUMIND_UPLOAD_TIMEOUT_MS` controls the upstream upload timeout and defaults to 120000 milliseconds. List requests use `DOCUMIND_API_TIMEOUT_MS`, defaulting to 10000 milliseconds. Restart the development server after configuration changes.

```bash
cp .env.example .env.local
npm run dev
```

The browser sends multipart data to the same-origin `/api/documents` route. Next.js streams the file to FastAPI's `/documents` endpoint, preserving backend validation errors. PostgreSQL, S3 storage, and FastAPI must be running. The backend remains responsible for upload size limits and actual PDF content validation. Browser checks are only early feedback.

Uploads are never retried automatically because an interrupted response does not guarantee that the backend did not save the file. Deployment proxies must permit the configured upload size and duration. Authentication screens, document processing, and question answering are separate milestones.

## Authentication proxy

Next.js exposes `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. These routes forward requests to the corresponding FastAPI `/auth` endpoints. Register and login accept JSON bodies up to 16 KiB. Authentication responses are not cached, and requests are not retried automatically.

The proxy preserves the backend session cookie and its attributes when logging in or out. Auth and document requests forward only the configured session cookie to FastAPI. Set `DOCUMIND_SESSION_COOKIE_NAME` to the same value in the frontend and backend; both default to `documind_session`. Configure the backend production environment to issue Secure cookies and serve the application over HTTPS.

Set `DOCUMIND_APP_ORIGIN` to the public frontend origin, such as `http://localhost:3000` locally or `https://app.example.com` in production. This is required in production, including behind a reverse proxy. In development, an omitted value defaults to the request URL's origin. Restart Next.js after changing environment variables.

All auth POST requests, document uploads, and document deletions require an `Origin` header matching that origin. Browser requests from the same frontend supply it automatically; HTTP scripts must supply it explicitly. Cross-origin mutations are rejected before reaching FastAPI. Deployments should keep FastAPI internal to the application network.

This milestone provides the server-side connection. Registration, login, and session-aware screens are the next milestone; the existing document screen requires an authenticated session.

## Frontend checks

Use Node.js 24. Run from the `frontend` directory:

```bash
npm run lint
npm test
npm run typecheck
npm run build
```

Component tests use Vitest, React Testing Library, and jsdom. They exercise selection, replacement, removal, upload states, and validation feedback. Node-environment tests verify multipart forwarding, backend errors, timeouts, and upload response validation.

## Document list API

`GET /documents?limit=10&offset=0` returns `items`, `has_more`, `limit`, and `offset`. Limits range from 1 to 100. Documents are ordered by creation time descending, then ID descending to break ties. Offset pagination is not a snapshot: concurrent uploads can shift page boundaries. Uploading from this page resets the list to its first page.
