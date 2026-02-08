# Birthday Invite Portal

Streamlit app for gated invites with Supabase storage.

## Local run

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Create `.streamlit/secrets.toml` with:

```
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
ADMIN_PASSWORD = "your-admin-password"
ADMIN_LINK_TOKEN = "your-admin-link-token"
MAILGUN_API_KEY = "your-mailgun-api-key"
MAILGUN_DOMAIN = "your-mailgun-domain"
MAILGUN_FROM_EMAIL = "your-verified-from-email"
```

3. Run:

```
streamlit run app.py
```

## Supabase setup

- Run the SQL in `supabase_schema.sql`.
- Insert your invite tokens into `public.invites`.

If you already ran the schema, run these to add the new columns/tables:

```
alter table public.invites add column if not exists flight_origin text;

alter table public.survey_responses add column if not exists budget_preference text;
alter table public.survey_responses add column if not exists email text;
alter table public.survey_responses add column if not exists notify_opt_in boolean default false;
alter table public.survey_responses add column if not exists passport_confirmed boolean default false;

create table if not exists public.trip_events (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  event_date date,
  event_time time,
  location text,
  description text,
  bring_items text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

alter table public.trip_events enable row level security;
create policy "service full access trip events" on public.trip_events
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
```

Example insert:

```
insert into public.invites (token, guest_name, video_url, needs_passport, home_city)
values
  ('abc123', 'Jay', 'https://youtu.be/your-video', true, 'JFK'),
  ('def456', 'Taylor', 'https://youtu.be/your-video-2', false, 'LAX');
```

## Gallery images

- Put your images in `assets/gallery` (jpg, png, webp).
- Optional: add remote image URLs in `GALLERY_URLS` inside `app.py`.

## Streamlit Cloud

- Add the same secrets in the Streamlit Cloud app settings.
- Deploy from this repository.

## Admin link

Open the admin dashboard with: `/?admin=YOUR_TOKEN`
Set `ADMIN_LINK_TOKEN` in secrets to your private token.

## Email notifications

- Guests can opt in for email updates in the survey.
- Admin can send 1-day reminders from the admin dashboard.
- Requires Mailgun API key, domain, and a verified `MAILGUN_FROM_EMAIL`.
