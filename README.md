# ATM – Dashboard

Jenny Lind | Artist Booking & Tour Management.

Initial Python/Streamlit dashboard, prepared for Google Cloud Run and Neon PostgreSQL.

## Local run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Google Cloud Run

Deploy from this GitHub repository with **Cloud Build**, using the included `Dockerfile`.
The app listens on `0.0.0.0` and Cloud Run's `PORT` (default 8080).

If Cloud Run was connected while the repository was empty, create or retry the deployment after these files appear.

## Neon configuration

Set `DATABASE_URL` using **Google Secret Manager / Cloud Run secrets**.
Do **not** commit credentials, environment files, client data, or invoice data to GitHub.

The dashboard starts without a database connection; its overview checks connectivity when `DATABASE_URL` is supplied. Database-backed pages are not implemented yet.

## Security

Before processing customer/contact/invoice data, restrict Cloud Run access and add application authentication/authorization. A public Cloud Run URL alone is **not** suitable for private ATM records.

## Deployment retry

A new commit on the `main` branch is intended to trigger the connected Google Cloud Build deployment for the `atmdashboard` service. Verify the actual build result in Google Cloud Console → Cloud Build → History.
