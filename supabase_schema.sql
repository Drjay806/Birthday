-- Core invite list
create table if not exists public.invites (
  token text primary key,
  guest_name text,
  video_url text,
  needs_passport boolean default false,
  home_city text,
  flight_origin text,
  gate_name_done boolean default false,
  gate_video_done boolean default false,
  rsvp_choice text,
  rsvp_done boolean default false,
  survey_done boolean default false,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Survey responses
create table if not exists public.survey_responses (
  id uuid primary key default gen_random_uuid(),
  token text references public.invites(token) on delete cascade,
  liquor_preferences text,
  event_preferences text,
  arrival_window text,
  plus_one text,
  budget_preference text,
  email text,
  notify_opt_in boolean default false,
  notes text,
  created_at timestamp with time zone default now()
);

-- Optional event log
create table if not exists public.invite_events (
  id uuid primary key default gen_random_uuid(),
  token text references public.invites(token) on delete cascade,
  event_type text not null,
  detail text,
  created_at timestamp with time zone default now()
);

-- Admin-managed trip events
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

create index if not exists idx_survey_token on public.survey_responses(token);
create index if not exists idx_events_token on public.invite_events(token);
create index if not exists idx_trip_events_date on public.trip_events(event_date);

-- Enable RLS and allow service key access from Streamlit
alter table public.invites enable row level security;
alter table public.survey_responses enable row level security;
alter table public.invite_events enable row level security;
alter table public.trip_events enable row level security;

-- Policies assume Streamlit uses a service role key stored in secrets
create policy "service full access invites" on public.invites
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

create policy "service full access survey" on public.survey_responses
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

create policy "service full access events" on public.invite_events
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

create policy "service full access trip events" on public.trip_events
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
