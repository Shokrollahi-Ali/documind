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

The homepage lets you select, replace, remove, and upload one PDF. It displays the saved document metadata after a successful upload. The latest result is held in page state and is cleared on reload; a persisted document list is not implemented yet.

Copy `.env.example` to `.env.local` in the frontend directory, then set `DOCUMIND_API_URL` to your FastAPI service URL. This variable is server-only. `DOCUMIND_UPLOAD_TIMEOUT_MS` controls the upstream upload timeout and defaults to 120000 milliseconds. Restart the development server after configuration changes.

```bash
cp .env.example .env.local
npm run dev
```

The browser sends multipart data to the same-origin `/api/documents` route. Next.js streams the file to FastAPI's `/documents` endpoint, preserving backend validation errors. PostgreSQL, S3 storage, and FastAPI must be running. The backend remains responsible for upload size limits and actual PDF content validation. Browser checks are only early feedback.

Uploads are never retried automatically because an interrupted response does not guarantee that the backend did not save the file. Deployment proxies must permit the configured upload size and duration. Authentication, document processing, and question answering are separate milestones.

## Frontend checks

Use Node.js 24. Run from the `frontend` directory:

```bash
npm run lint
npm test
npm run typecheck
npm run build
```

Component tests use Vitest, React Testing Library, and jsdom. They exercise selection, replacement, removal, upload states, and validation feedback. Node-environment tests verify multipart forwarding, backend errors, timeouts, and upload response validation.
