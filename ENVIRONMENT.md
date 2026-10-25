# Backend environment variables (Render)

Set these on the Render service (Environment tab). "Required" means the
backend will not work properly without it; "optional" ones switch a feature
on or override a default.

## Required

| Variable | What it is |
| --- | --- |
| `SECRET_KEY` | Django secret key (long random string). |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database (port defaults to 5432). |
| `REDIS_URL` | Redis for Celery, websockets and cache, e.g. `redis://…:6379/1`. |
| `PAYSTACK_SECRET_KEY` | Paystack live secret key (payments and payouts). |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Brevo SMTP login (Brevo → SMTP & API → SMTP). `EMAIL_HOST` defaults to `smtp-relay.brevo.com`, `EMAIL_PORT` to 587. |
| `CLOUDINARY_STORAGE_CLOUD_NAME`, `CLOUDINARY_STORAGE_API_KEY`, `CLOUDINARY_STORAGE_API_SECRET` | Image uploads. |
| `BACKBLAZE_APPLICATION_KEY_ID`, `BACKBLAZE_APPLICATION_KEY`, `BACKBLAZE_BUCKET_ID`, `BACKBLAZE_BUCKET_NAME` | Document/file storage. |
| `FIREBASE_CREDENTIALS_PATH` | Path to the Firebase admin JSON (push notifications). Default `findmytaste-firebase-adminsdk.json`. |

## Phone verification by SMS (Termii)

Phone codes are only used when **both** of these are set; otherwise the apps
skip the phone step and use email codes.

| Variable | What it is |
| --- | --- |
| `TERMII_API_KEY` | Live key from app.termii.ai → Settings → API Keys. |
| `PHONE_VERIFICATION_REQUIRED` | `True` to switch phone verification on. |
| `TERMII_SENDER_ID` | Approved sender ID (default `N-Alert`). |
| `TERMII_CHANNEL` | `dnd` (default, reaches DND numbers) or `generic`. |
| `TERMII_BASE_URL` | Only if Termii gives you a different API host. |

## Sign-in

| Variable | What it is |
| --- | --- |
| `GOOGLE_OAUTH_CLIENT_IDS` | Comma-separated Google client IDs allowed to sign in. Defaults to the web + iOS clients already in the code. |
| `APPLE_CLIENT_IDS` | Comma-separated Apple bundle IDs (default `com.findmytaste.customer`). Add the vendor/rider bundle IDs if they use Sign in with Apple. |
| `JWT_SIGNING_KEY` | Optional; defaults to `SECRET_KEY`. |

## Optional

| Variable | What it is |
| --- | --- |
| `PUBLIC_API_BASE_URL` | Public backend URL used in email links (default `https://findmytaste-image-latest.onrender.com`). |
| `DEFAULT_FROM_EMAIL` | Default sender (default `support@findmytaste.com.ng`). |
| `CAMPAIGN_EMAIL_HOST`, `CAMPAIGN_EMAIL_PORT`, `CAMPAIGN_EMAIL_USER`, `CAMPAIGN_EMAIL_PASSWORD` | Only if admin email campaigns should go through another SMTP server instead of Brevo. Not needed when campaigns are sent from Brevo directly (export contacts from the admin's Email Campaigns page). |
| `GOOGLE_MAPS_API_KEY` | Server-side distance/directions. |
| `OPENWEATHER_API_KEY` | Weather-based features. |
| `FLUTTERWAVE_AUTH_TOKEN` | Only if Flutterwave is used. |
| `DEBUG` | Leave unset (False) in production. |
