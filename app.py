import os
from datetime import datetime, date, time, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests
from requests.auth import HTTPBasicAuth
from supabase_client import get_supabase_client


APP_TITLE = "Costa Rica Trip"
DEST_CITY = "Liberia, Costa Rica"
DEST_IATA = "LIR"
EVENT_NAME = "Costa Rica Trip"
EVENT_START_DATE = date(2026, 6, 11)
EVENT_END_DATE = date(2026, 6, 17)
EVENT_START_TIME = time(19, 0)
ALLOW_RSVP_REDO = False
GALLERY_DIR = "assets/gallery"
GALLERY_URLS = []
DEFAULT_ORIGIN = "NYC"
PASSPORT_STANDARD_WEEKS = 13
PASSPORT_EXPEDITED_WEEKS = 7
WEATHER_AVG_HIGH_F = 84
WEATHER_AVG_LOW_F = 70
WEATHER_NOTE = "June is warm and humid with afternoon showers."
ADMIN_LINK_PARAM = "admin"
AUTO_REFRESH_SECONDS = 60
AVG_PRICE_ORIGINS = {
    "Nashville (BNA)": 520,
    "Washington DC (WAS)": 540,
    "Houston (HOU)": 480,
    "Orlando (MCO)": 460,
    "Dallas (DFW)": 500,
}
ORIGIN_ALIASES = {
    "nashville": "BNA",
    "nashville tn": "BNA",
    "washington dc": "WAS",
    "dc": "WAS",
    "houston": "HOU",
    "houston tx": "HOU",
    "orlando": "MCO",
    "orlando fl": "MCO",
    "dallas": "DFW",
    "dallas tx": "DFW",
}


st.set_page_config(page_title=APP_TITLE, page_icon="✈️", layout="wide")


def apply_modern_theme():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600&family=Playfair+Display:wght@500;600&display=swap');
        .stApp {
            background: radial-gradient(circle at 10% 10%, rgba(199,220,255,0.4), transparent 35%),
                        radial-gradient(circle at 90% 10%, rgba(255,229,199,0.5), transparent 38%),
                        #f4f5f7;
        }
        h1, h2, h3, h4, h5, h6, .hero-title {
            font-family: 'Playfair Display', serif;
            letter-spacing: -0.02em;
        }
        p, li, span, div, label, input, textarea {
            font-family: 'Manrope', sans-serif;
        }
        .hero {
            padding: 28px 32px;
            background: #ffffff;
            border: 1px solid #e6e8ec;
            border-radius: 20px;
            box-shadow: 0 12px 30px rgba(17, 24, 39, 0.08);
            margin-bottom: 24px;
        }
        .hero-eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 12px;
            color: #4b5563;
            margin-bottom: 10px;
        }
        .hero-title {
            font-size: 40px;
            margin: 0 0 8px 0;
            color: #0f172a;
        }
        .hero-subtitle {
            font-size: 16px;
            color: #334155;
            margin-bottom: 12px;
        }
        .card {
            background: #ffffff;
            border: 1px solid #e6e8ec;
            border-radius: 18px;
            padding: 18px 20px;
            box-shadow: 0 10px 24px rgba(17, 24, 39, 0.06);
        }
        .card-grid {
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        }
        .pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            background: #eef2ff;
            color: #312e81;
        }
        .section-title {
            margin-top: 24px;
        }
        img {
            border-radius: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_token_from_query():
    qp = st.query_params
    token = qp.get("t") or qp.get("token")
    if isinstance(token, list):
        return token[0]
    return token


def set_token_in_query(token):
    st.query_params["t"] = token


def is_admin_request():
    admin_token = st.secrets.get("ADMIN_LINK_TOKEN", os.environ.get("ADMIN_LINK_TOKEN"))
    if not admin_token:
        return False
    provided = st.query_params.get(ADMIN_LINK_PARAM)
    if isinstance(provided, list):
        provided = provided[0]
    return provided == admin_token


def load_invite(supabase, token):
    res = supabase.table("invites").select("*").eq("token", token).single().execute()
    if res.data:
        return res.data
    return None


def update_invite(supabase, token, payload):
    payload["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("invites").update(payload).eq("token", token).execute()


def log_event(supabase, token, event_type, detail=""):
    supabase.table("invite_events").insert(
        {"token": token, "event_type": event_type, "detail": detail}
    ).execute()


def blackout_screen(message):
    st.markdown(
        """
        <style>
        body { background-color: #000000; color: #f2f2f2; }
        .blackout { text-align: center; padding: 80px 20px; font-size: 24px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='blackout'>{message}</div>", unsafe_allow_html=True)


def ics_payload(extra_events=None):
    start_dt = datetime.combine(EVENT_START_DATE, EVENT_START_TIME)
    end_dt = datetime.combine(EVENT_END_DATE, EVENT_START_TIME)
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = f"{EVENT_NAME.replace(' ', '')}-{start_dt.strftime('%Y%m%d')}@invite"
    ics = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Birthday Invite//EN\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}\n"
        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}\n"
        f"SUMMARY:{EVENT_NAME}\n"
        f"LOCATION:{DEST_CITY}\n"
        "END:VEVENT\n"
    )
    for event in extra_events or []:
        event_date = event.get("event_date")
        event_time = event.get("event_time") or time(18, 0)
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)
        if isinstance(event_time, str):
            event_time = time.fromisoformat(event_time)
        if not event_date:
            continue
        event_start = datetime.combine(event_date, event_time)
        event_uid = f"{event.get('id', 'event')}-{event_start.strftime('%Y%m%d')}@invite"
        title = event.get("title") or "Trip Event"
        location = event.get("location") or DEST_CITY
        ics += (
            "BEGIN:VEVENT\n"
            f"UID:{event_uid}\n"
            f"DTSTAMP:{dtstamp}\n"
            f"DTSTART:{event_start.strftime('%Y%m%dT%H%M%S')}\n"
            f"SUMMARY:{title}\n"
            f"LOCATION:{location}\n"
            "END:VEVENT\n"
        )
    ics += "END:VCALENDAR\n"
    return ics


def flights_link(home_city):
    raw_origin = (home_city or DEFAULT_ORIGIN).strip()
    origin_key = raw_origin.lower()
    origin = ORIGIN_ALIASES.get(origin_key, raw_origin).upper().replace(" ", "")
    start = EVENT_START_DATE.strftime("%Y-%m-%d")
    end = EVENT_END_DATE.strftime("%Y-%m-%d")
    dest = DEST_IATA.upper()
    return f"https://www.kayak.com/flights/{origin}-{dest}/{start}/{end}?sort=bestflight_a"


def flights_embed(home_city):
    url = flights_link(home_city)
    st.markdown(
        f"""
        <div class="card">
            <div class="pill">Kayak</div>
            <h3>Live results</h3>
            <p>Open the live search to see real-time routes and prices.</p>
            <a href="{url}" target="_blank">View live flights</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_gallery_images():
    images = []
    if os.path.isdir(GALLERY_DIR):
        for name in sorted(os.listdir(GALLERY_DIR)):
            lower = name.lower()
            if lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                images.append(os.path.join(GALLERY_DIR, name))
    images.extend(GALLERY_URLS)
    return images


def caption_from_filename(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace("_", " ").replace("-", " ").title()


def passport_timeline():
    today = date.today()
    days_to_trip = (EVENT_START_DATE - today).days
    standard_deadline = EVENT_START_DATE - timedelta(weeks=PASSPORT_STANDARD_WEEKS)
    expedited_deadline = EVENT_START_DATE - timedelta(weeks=PASSPORT_EXPEDITED_WEEKS)
    standard_left = (standard_deadline - today).days
    expedited_left = (expedited_deadline - today).days

    st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="card">
            <div class="pill">Trip countdown</div>
            <h3>{max(days_to_trip, 0)} days</h3>
            <p>Until departure on {EVENT_START_DATE.strftime('%B %d, %Y')}.</p>
        </div>
        <div class="card">
            <div class="pill">Standard processing</div>
            <h3>{standard_deadline.strftime('%b %d, %Y')}</h3>
            <p>{'Deadline has passed.' if standard_left < 0 else f'{standard_left} days left to apply.'}</p>
        </div>
        <div class="card">
            <div class="pill">Expedited</div>
            <h3>{expedited_deadline.strftime('%b %d, %Y')}</h3>
            <p>{'Deadline has passed.' if expedited_left < 0 else f'{expedited_left} days left to apply.'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        **Passport steps**
        1. Gather documents and take a passport photo.
        2. Fill out the application and pay the fee.
        3. Schedule an in-person appointment.
        4. Track your application status.

        **Official links (US)**
        - https://travel.state.gov/content/travel/en/passports/how-apply.html
        - https://travel.state.gov/content/travel/en/passports/need-passport/apply-in-person.html
        - https://travel.state.gov/content/travel/en/passports/need-passport/status.html
        """
    )


def weather_section():
    st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="card">
            <div class="pill">Average high</div>
            <h3>{WEATHER_AVG_HIGH_F}°F</h3>
            <p>Warm afternoons in June.</p>
        </div>
        <div class="card">
            <div class="pill">Average low</div>
            <h3>{WEATHER_AVG_LOW_F}°F</h3>
            <p>Humidity stays elevated.</p>
        </div>
        <div class="card">
            <div class="pill">Quick note</div>
            <h3>{WEATHER_NOTE}</h3>
            <p>Check the 10-day forecast before you pack.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def auto_refresh():
    components.html(
        f"""
        <script>
        setTimeout(() => window.location.reload(), {AUTO_REFRESH_SECONDS * 1000});
        </script>
        """,
        height=0,
    )


def parse_items(raw_items):
    if not raw_items:
        return []
    lines = []
    for part in str(raw_items).split("\n"):
        lines.extend([item.strip() for item in part.split(",")])
    return [item for item in lines if item]


def load_events(supabase):
    res = (
        supabase.table("trip_events")
        .select("*")
        .order("event_date")
        .order("event_time")
        .execute()
    )
    return res.data or []


def format_event_line(event):
    event_date = event.get("event_date")
    event_time = event.get("event_time")
    if isinstance(event_date, str):
        event_date = date.fromisoformat(event_date)
    if isinstance(event_time, str):
        event_time = time.fromisoformat(event_time)
    date_text = event_date.strftime("%b %d") if event_date else ""
    time_text = event_time.strftime("%I:%M %p").lstrip("0") if event_time else ""
    title = event.get("title") or "Trip Event"
    location = event.get("location") or ""
    pieces = [piece for piece in [title, time_text, location] if piece]
    return f"{date_text} - " + " · ".join(pieces)


def send_bulk_email(recipients, subject, content):
    api_key = st.secrets.get("MAILGUN_API_KEY", os.environ.get("MAILGUN_API_KEY"))
    domain = st.secrets.get("MAILGUN_DOMAIN", os.environ.get("MAILGUN_DOMAIN"))
    from_email = st.secrets.get("MAILGUN_FROM_EMAIL", os.environ.get("MAILGUN_FROM_EMAIL"))
    if not api_key or not domain or not from_email:
        st.error("Missing Mailgun settings. Set MAILGUN_API_KEY, MAILGUN_DOMAIN, and MAILGUN_FROM_EMAIL.")
        return False

    if not recipients:
        st.warning("No guests have opted in for email updates.")
        return False

    for email in recipients:
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=HTTPBasicAuth("api", api_key),
            data={
                "from": from_email,
                "to": email,
                "subject": subject,
                "text": content,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            st.error(f"Mailgun error for {email}: {response.text}")
            return False
    return True


def get_opted_in_emails(supabase):
    opted = (
        supabase.table("survey_responses")
        .select("email, notify_opt_in")
        .eq("notify_opt_in", True)
        .execute()
    )
    return [row.get("email") for row in (opted.data or []) if row.get("email")]


def send_event_reminders(recipients, events):
    if not events:
        st.warning("No upcoming events to notify.")
        return False

    subject = f"{EVENT_NAME} update: events tomorrow"
    event_lines = "\n".join([format_event_line(event) for event in events])
    content = (
        f"Hi!\n\nHere are the events happening tomorrow for {EVENT_NAME}:\n\n"
        f"{event_lines}\n\n"
        "See you there!"
    )
    return send_bulk_email(recipients, subject, content)


def send_passport_deadline_reminder(recipients):
    standard_deadline = EVENT_START_DATE - timedelta(weeks=PASSPORT_STANDARD_WEEKS)
    subject = f"Passport reminder: {EVENT_NAME}"
    content = (
        "Hi!\n\n"
        f"Reminder: standard passport processing should be started by {standard_deadline.strftime('%B %d, %Y')}.\n"
        "If you have not applied yet, please make plans now.\n\n"
        "Passport info: https://travel.state.gov/content/travel/en/passports/how-apply.html\n\n"
        "See you soon!"
    )
    return send_bulk_email(recipients, subject, content)


def admin_dashboard(supabase):
    st.subheader("Admin Dashboard")
    invites_res = supabase.table("invites").select("*").execute()
    survey_res = supabase.table("survey_responses").select("*").execute()

    invites = invites_res.data or []
    survey = survey_res.data or []

    invites_df = pd.DataFrame(invites)
    survey_df = pd.DataFrame(survey)

    st.subheader("RSVP Overview")
    if not invites_df.empty:
        rsvp_counts = invites_df["rsvp_choice"].value_counts(dropna=False)
        st.bar_chart(rsvp_counts)
        st.dataframe(invites_df, use_container_width=True)
        csv_invites = invites_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download invites CSV", csv_invites, "invites.csv", "text/csv")
    else:
        st.info("No invites found.")

    st.subheader("Survey Responses")
    if not survey_df.empty:
        st.dataframe(survey_df, use_container_width=True)
        csv_survey = survey_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download survey CSV", csv_survey, "survey.csv", "text/csv")
    else:
        st.info("No survey responses yet.")

    st.subheader("Notifications")
    reminder_day = date.today() + timedelta(days=1)
    upcoming = [event for event in load_events(supabase) if event.get("event_date") in {reminder_day.isoformat(), reminder_day}]
    recipient_emails = get_opted_in_emails(supabase)

    st.write(f"Events tomorrow: {len(upcoming)}")
    st.write(f"Opted-in emails: {len(recipient_emails)}")
    if st.button("Send 1-day reminders"):
        if send_event_reminders(recipient_emails, upcoming):
            st.success("Reminder emails sent.")
    if st.button("Send passport deadline reminder"):
        if send_passport_deadline_reminder(recipient_emails):
            st.success("Passport reminder sent.")


def admin_events_manager(supabase):
    st.subheader("Trip Calendar")
    with st.form("event_form"):
        title = st.text_input("Event title")
        event_date = st.date_input("Event date")
        event_time = st.time_input("Event time", value=time(18, 0))
        location = st.text_input("Location")
        description = st.text_area("Description")
        bring_items = st.text_area("Things to bring (comma or line separated)")
        submitted = st.form_submit_button("Add event")

    if submitted and title:
        supabase.table("trip_events").insert(
            {
                "title": title,
                "event_date": event_date.isoformat() if event_date else None,
                "event_time": event_time.strftime("%H:%M:%S") if event_time else None,
                "location": location,
                "description": description,
                "bring_items": bring_items,
            }
        ).execute()
        st.success("Event added.")
        recipient_emails = get_opted_in_emails(supabase)
        subject = f"New event added: {title}"
        content = (
            f"Hi!\n\nA new event was added to {EVENT_NAME}:\n\n"
            f"{title}\n"
            f"{event_date.strftime('%B %d, %Y') if event_date else ''} {event_time.strftime('%I:%M %p').lstrip('0') if event_time else ''}\n"
            f"{location}\n\n"
            "Check your invite for details."
        )
        send_bulk_email(recipient_emails, subject, content)

    events = load_events(supabase)
    if not events:
        st.info("No events yet.")
        return

    st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
    for event in events:
        items = parse_items(event.get("bring_items"))
        date_value = event.get("event_date")
        if isinstance(date_value, str):
            date_value = date.fromisoformat(date_value)
        date_text = date_value.strftime("%B %d") if date_value else ""
        st.markdown(
            f"""
            <div class="card">
                <div class="pill">{date_text}</div>
                <h3>{event.get('title')}</h3>
                <p>{event.get('location') or ''}</p>
                <p>{event.get('description') or ''}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if items:
            st.write("Bring:")
            st.write(", ".join(items))

        with st.expander("Edit event"):
            with st.form(f"edit_event_{event.get('id')}"):
                edit_title = st.text_input("Event title", value=event.get("title") or "")
                edit_date = st.date_input("Event date", value=date_value or EVENT_START_DATE)
                raw_time = event.get("event_time")
                edit_time = time.fromisoformat(raw_time) if raw_time else time(18, 0)
                edit_time = st.time_input("Event time", value=edit_time)
                edit_location = st.text_input("Location", value=event.get("location") or "")
                edit_description = st.text_area("Description", value=event.get("description") or "")
                edit_bring = st.text_area(
                    "Things to bring (comma or line separated)",
                    value=event.get("bring_items") or "",
                )
                saved = st.form_submit_button("Save changes")

            if saved:
                supabase.table("trip_events").update(
                    {
                        "title": edit_title,
                        "event_date": edit_date.isoformat() if edit_date else None,
                        "event_time": edit_time.strftime("%H:%M:%S") if edit_time else None,
                        "location": edit_location,
                        "description": edit_description,
                        "bring_items": edit_bring,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                ).eq("id", event.get("id")).execute()
                st.success("Event updated.")
                st.rerun()

        if st.button("Delete", key=f"delete_{event.get('id')}"):
            supabase.table("trip_events").delete().eq("id", event.get("id")).execute()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def main():
    apply_modern_theme()
    st.title(APP_TITLE)
    st.caption("Private invite portal")

    supabase = get_supabase_client()
    if is_admin_request():
        admin_dashboard(supabase)
        admin_events_manager(supabase)
        return

    token = get_token_from_query()
    if not token:
        st.info("Enter your invite code to continue.")
        input_token = st.text_input("Invite code")
        if input_token:
            set_token_in_query(input_token.strip())
            st.rerun()
        return

    invite = load_invite(supabase, token)
    if not invite:
        st.error("Invalid invite code. Please check your link.")
        return

    rsvp_done = invite.get("rsvp_done")
    rsvp_choice = invite.get("rsvp_choice")

    if rsvp_done and rsvp_choice == "no" and not ALLOW_RSVP_REDO:
        blackout_screen("Thanks for letting us know. We will miss you!")
        return

    if rsvp_done and rsvp_choice in {"yes", "maybe"}:
        render_full_hub(supabase, invite)
        return

    if not invite.get("gate_name_done"):
        render_name_gate(supabase, invite)
        return

    if not invite.get("gate_video_done"):
        render_video_gate(supabase, invite)
        return

    render_rsvp_gate(supabase, invite)


def render_name_gate(supabase, invite):
    st.header("Grand Entrance")
    st.write("Welcome. Please confirm your name to open the invite.")
    name = st.text_input("Your name", value=invite.get("guest_name") or "")
    if st.button("Enter"):
        if not name.strip():
            st.error("Please enter your name.")
            return
        update_invite(supabase, invite["token"], {"guest_name": name.strip(), "gate_name_done": True})
        log_event(supabase, invite["token"], "gate_name_done")
        st.rerun()


def render_video_gate(supabase, invite):
    st.header("Video Gate")
    st.write("A quick message just for you.")
    video_url = invite.get("video_url")
    if video_url:
        st.video(video_url)
    else:
        st.info("Video coming soon.")
    if st.button("I watched it"):
        update_invite(supabase, invite["token"], {"gate_video_done": True})
        log_event(supabase, invite["token"], "gate_video_done")
        st.rerun()


def render_rsvp_gate(supabase, invite):
    st.header("RSVP")
    st.write("Let us know if you can make it.")
    with st.form("rsvp_form"):
        choice = st.radio("Your response", ["yes", "maybe", "no"], index=0)
        submitted = st.form_submit_button("Submit RSVP")

    if not submitted:
        return

    update_invite(
        supabase,
        invite["token"],
        {"rsvp_done": True, "rsvp_choice": choice},
    )
    log_event(supabase, invite["token"], "rsvp_done", choice)

    if choice == "no" and not ALLOW_RSVP_REDO:
        blackout_screen("Thanks for letting us know. We will miss you!")
        return

    st.rerun()


def render_full_hub(supabase, invite):
    auto_refresh()
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-eyebrow">{EVENT_NAME}</div>
            <div class="hero-title">{DEST_CITY}</div>
            <div class="hero-subtitle">June 11-17, 2026 · Sun, sand, and a long weekend together.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<h2 class='section-title'>Flights</h2>", unsafe_allow_html=True)
    st.write("Live results from Skyscanner for your dates.")
    st.markdown("**Estimated average round-trip prices**")
    price_cols = st.columns(5)
    for idx, (label, price) in enumerate(AVG_PRICE_ORIGINS.items()):
        price_cols[idx].markdown(
            f"<div class='card'><div class='pill'>{label}</div><h3>${price}</h3><p>Estimate</p></div>",
            unsafe_allow_html=True,
        )
    default_origin = invite.get("flight_origin") or invite.get("home_city") or DEFAULT_ORIGIN

    def save_origin():
        value = st.session_state.get("flight_origin_input", "").strip().upper()
        if value and value != invite.get("flight_origin"):
            update_invite(supabase, invite["token"], {"flight_origin": value})
            log_event(supabase, invite["token"], "flight_origin_update", value)

    origin_input = st.text_input(
        "Origin airport or city",
        value=default_origin,
        key="flight_origin_input",
        on_change=save_origin,
    )
    origin_value = origin_input.strip() or default_origin
    flights_embed(origin_value)

    st.markdown("<h2 class='section-title'>Passport & Timing</h2>", unsafe_allow_html=True)
    if invite.get("needs_passport"):
        st.write("Make sure your passport is valid and in hand before the trip.")
    else:
        st.write("If you need a passport, here is the timeline and steps.")
    passport_timeline()

    st.markdown("<h2 class='section-title'>Weather</h2>", unsafe_allow_html=True)
    weather_section()

    st.markdown("<h2 class='section-title'>Add to Calendar</h2>", unsafe_allow_html=True)
    events = load_events(supabase)
    ics = ics_payload(events)
    st.download_button(
        "Download calendar invite",
        data=ics,
        file_name="costa-rica-trip.ics",
        mime="text/calendar",
    )

    if events:
        st.markdown("<h2 class='section-title'>Itinerary & What to Bring</h2>", unsafe_allow_html=True)
        st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
        for event in events:
            items = parse_items(event.get("bring_items"))
            date_value = event.get("event_date")
            if isinstance(date_value, str):
                date_value = date.fromisoformat(date_value)
            date_text = date_value.strftime("%B %d") if date_value else ""
            st.markdown(
                f"""
                <div class="card">
                    <div class="pill">{date_text}</div>
                    <h3>{event.get('title')}</h3>
                    <p>{event.get('location') or ''}</p>
                    <p>{event.get('description') or ''}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if items:
                st.write("Bring:")
                st.write(", ".join(items))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<h2 class='section-title'>Gallery</h2>", unsafe_allow_html=True)
    gallery_images = get_gallery_images()
    if gallery_images:
        cols = st.columns(4)
        for idx, image in enumerate(gallery_images):
            cols[idx % 4].image(image, use_container_width=True, caption=caption_from_filename(image))
    else:
        st.write("Costa Rica vibes and villa photos coming soon.")

    if not invite.get("survey_done"):
        st.subheader("Quick Survey")
        render_survey(supabase, invite)
    else:
        st.success("Survey completed. Thank you!")


def render_survey(supabase, invite):
    with st.form("survey_form"):
        liquor = st.multiselect(
            "Liquor preferences",
            ["Vodka", "Tequila", "Whiskey", "Rum", "Gin", "Champagne", "Wine", "Non-drinker"],
        )
        events = st.multiselect(
            "Event preferences",
            ["Club", "Brunch", "Day party", "Chill night", "Excursion", "Beach", "Pool"],
        )
        events_other = st.text_input("Other event preferences (optional)")
        arrival = st.selectbox(
            "Arrival window",
            ["June 10", "June 11", "June 12", "June 13", "Not sure"],
        )
        plus_one = st.selectbox("Plus-one", ["No", "Yes", "Maybe"])
        budget = st.selectbox(
            "Preferred spend per event",
            ["Under $50", "$50-$100", "$100-$200", "$200+"],
        )
        email = st.text_input("Email for trip updates")
        notify_opt_in = st.checkbox("Yes, email me updates about events")
        notes = st.text_area("Recommendations for events or games")
        submitted = st.form_submit_button("Submit survey")

    if not submitted:
        return

    event_list = list(events)
    if events_other.strip():
        event_list.append(events_other.strip())

    supabase.table("survey_responses").insert(
        {
            "token": invite["token"],
            "liquor_preferences": ", ".join(liquor),
            "event_preferences": ", ".join(event_list),
            "arrival_window": arrival,
            "plus_one": plus_one,
            "budget_preference": budget,
            "email": email.strip(),
            "notify_opt_in": notify_opt_in,
            "notes": notes,
        }
    ).execute()
    update_invite(supabase, invite["token"], {"survey_done": True})
    log_event(supabase, invite["token"], "survey_done")
    st.rerun()


if __name__ == "__main__":
    main()
