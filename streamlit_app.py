import hashlib
import json
import os
import sqlite3
import secrets
from io import BytesIO
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import streamlit as st
from pypdf import PdfReader

DB_PATH = "streamlit_job_platform.db"
SKILL_KEYWORDS = {
    "python", "fastapi", "flask", "django", "react", "javascript", "typescript",
    "sql", "docker", "aws", "node", "html", "css", "api", "backend", "frontend",
    "java", "spring", "kubernetes", "git", "postgresql", "mongodb", "redis",
}


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          cv_filename TEXT,
          cv_text TEXT,
          preferences_json TEXT DEFAULT '{}'
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def db_get_user_by_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, password_hash, cv_filename, cv_text, preferences_json FROM users WHERE email = ?",
        (email.lower().strip(),),
    )
    row = cur.fetchone()
    conn.close()
    return row


def db_create_user(name: str, email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name.strip(), email.lower().strip(), hash_password(password)),
    )
    conn.commit()
    conn.close()


def db_update_cv(user_id: int, filename: str, cv_text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET cv_filename = ?, cv_text = ? WHERE id = ?",
        (filename, cv_text, user_id),
    )
    conn.commit()
    conn.close()


def db_update_preferences(user_id: int, preferences: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET preferences_json = ? WHERE id = ?",
        (json.dumps(preferences), user_id),
    )
    conn.commit()
    conn.close()


def db_get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, password_hash, cv_filename, cv_text, preferences_json FROM users WHERE id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def db_create_auth_token(user_id: int) -> str:
    token = secrets.token_hex(24)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO auth_tokens (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token


def db_get_user_id_by_token(token: str) -> int | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM auth_tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return int(row[0])


def db_delete_auth_token(token: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def parse_uploaded_cv(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    suffix = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if suffix.endswith(".txt"):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="ignore")
    if suffix.endswith(".pdf"):
        reader = PdfReader(BytesIO(raw))
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n".join(text).strip()
    return ""


def tokenize(value: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return {token for token in cleaned.split() if len(token) > 1}


def extract_keywords(cv_text: str) -> list[str]:
    tokens = [token for token in tokenize(cv_text) if token not in {"with", "from", "this", "that", "and"}]
    return sorted(tokens)[:12]


def http_get_json(url: str, headers: dict | None = None) -> dict:
    merged = {"User-Agent": "Mozilla/5.0"}
    if headers:
        merged.update(headers)
    request = Request(url, headers=merged)
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def scrape_remoteok_jobs(preferences: dict, cv_text: str, limit: int = 20) -> list[dict]:
    query_bits = [preferences.get("job_title") or "", preferences.get("city") or "", preferences.get("country") or ""]
    if not any(query_bits):
        query_bits.append("software")
    query_bits.extend(extract_keywords(cv_text)[:4])
    terms = [t.lower() for t in " ".join([x for x in query_bits if x]).split() if t]

    request = Request("https://remoteok.com/remote-dev-jobs.rss", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:  # nosec B310
        xml_payload = response.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_payload)
    results = []
    for row in root.findall(".//item"):
        title = (row.findtext("title") or "Remote Role").strip()
        apply_url = (row.findtext("link") or "").strip()
        description = (row.findtext("description") or "").strip()
        blob = f"{title} {description}".lower()
        if terms and not any(t in blob for t in terms[:4]):
            continue
        results.append(
            {
                "source": "scrape_remoteok",
                "external_id": apply_url or title,
                "title": title,
                "company": "RemoteOK",
                "location": "Remote",
                "country": preferences.get("country") or "",
                "city": preferences.get("city") or "",
                "work_mode": "remote",
                "apply_url": apply_url,
                "description": description,
                "skills": sorted(tokenize(description) & SKILL_KEYWORDS),
            }
        )
        if len(results) >= limit:
            break
    return results


def scrape_weworkremotely_jobs(preferences: dict, cv_text: str, limit: int = 20) -> list[dict]:
    query_bits = [preferences.get("job_title") or "", preferences.get("city") or "", preferences.get("country") or ""]
    if not any(query_bits):
        query_bits.append("software")
    query_bits.extend(extract_keywords(cv_text)[:4])
    terms = [t.lower() for t in " ".join([x for x in query_bits if x]).split() if t]

    request = Request("https://weworkremotely.com/remote-jobs.rss", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:  # nosec B310
        xml_payload = response.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_payload)
    results = []
    for row in root.findall(".//item"):
        title = (row.findtext("title") or "Remote Role").strip()
        apply_url = (row.findtext("link") or "").strip()
        description = (row.findtext("description") or "").strip()
        blob = f"{title} {description}".lower()
        if terms and not any(t in blob for t in terms[:4]):
            continue
        results.append(
            {
                "source": "scrape_weworkremotely",
                "external_id": apply_url or title,
                "title": title,
                "company": "WeWorkRemotely",
                "location": "Remote",
                "country": preferences.get("country") or "",
                "city": preferences.get("city") or "",
                "work_mode": "remote",
                "apply_url": apply_url,
                "description": description,
                "skills": sorted(tokenize(description) & SKILL_KEYWORDS),
            }
        )
        if len(results) >= limit:
            break
    return results


def fetch_adzuna_jobs(preferences: dict, cv_text: str, limit: int = 20) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        return []
    country_map = {
        "de": "de", "germany": "de", "us": "us", "usa": "us", "united states": "us",
        "gb": "gb", "uk": "gb", "united kingdom": "gb",
    }
    country = country_map.get((preferences.get("country") or "de").strip().lower(), "de")
    city = (preferences.get("city") or "").strip()
    query_bits = [preferences.get("job_title") or "", preferences.get("work_mode") or ""]
    query_bits.extend(extract_keywords(cv_text)[:6])
    query = " ".join([x for x in query_bits if x]).strip() or "software engineer"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max(limit, 1), 50),
        "what": query,
        "content-type": "application/json",
    }
    if city:
        params["where"] = city
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{urlencode(params)}"
    data = http_get_json(url)
    results = []
    for row in data.get("results", []):
        desc = row.get("description") or ""
        location = row.get("location", {}).get("display_name") or "Unknown"
        blob = f"{row.get('title') or ''} {desc} {location}".lower()
        detected_mode = "remote" if "remote" in blob else ("hybrid" if "hybrid" in blob else "on-site")
        pref_mode = (preferences.get("work_mode") or "").lower().strip()
        if pref_mode and pref_mode != detected_mode and not (pref_mode == "on-site" and detected_mode == "on-site"):
            continue
        results.append(
            {
                "source": "adzuna",
                "external_id": str(row.get("id") or ""),
                "title": row.get("title") or "Unknown role",
                "company": (row.get("company") or {}).get("display_name") or "Unknown company",
                "location": location,
                "country": preferences.get("country") or "",
                "city": city,
                "work_mode": detected_mode,
                "apply_url": row.get("redirect_url"),
                "description": desc,
                "skills": sorted(tokenize(desc) & SKILL_KEYWORDS),
            }
        )
    return results


def fetch_jsearch_jobs(preferences: dict, cv_text: str, limit: int = 20) -> list[dict]:
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        return []
    query_bits = [
        preferences.get("job_title") or "",
        preferences.get("city") or "",
        preferences.get("country") or "",
        preferences.get("work_mode") or "",
    ]
    query_bits.extend(extract_keywords(cv_text)[:6])
    query = " ".join([x for x in query_bits if x]).strip() or "software engineer"
    params = {"query": query, "page": "1", "num_pages": "1"}
    url = f"https://jsearch.p.rapidapi.com/search?{urlencode(params)}"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    data = http_get_json(url, headers=headers)
    results = []
    for row in data.get("data", [])[:limit]:
        remote = bool(row.get("job_is_remote"))
        detected_mode = "remote" if remote else "on-site"
        pref_mode = (preferences.get("work_mode") or "").lower().strip()
        if pref_mode and pref_mode not in {detected_mode, "hybrid"}:
            continue
        description = row.get("job_description") or ""
        location = ", ".join([x for x in [row.get("job_city"), row.get("job_country")] if x]) or "Unknown"
        results.append(
            {
                "source": "jsearch",
                "external_id": str(row.get("job_id") or ""),
                "title": row.get("job_title") or "Unknown role",
                "company": row.get("employer_name") or "Unknown company",
                "location": location,
                "country": row.get("job_country") or "",
                "city": row.get("job_city") or "",
                "work_mode": detected_mode,
                "apply_url": row.get("job_apply_link"),
                "description": description,
                "skills": sorted(tokenize(description) & SKILL_KEYWORDS),
            }
        )
    return results


def fetch_real_jobs(preferences: dict, cv_text: str, limit: int = 20) -> list[dict]:
    provider = os.getenv("JOB_API_PROVIDER", "scrape").strip().lower()
    if provider in {"scrape", "scraping", "webscrape", "web-scrape"}:
        rows = []
        try:
            rows.extend(scrape_remoteok_jobs(preferences, cv_text, limit=limit))
        except Exception:
            pass
        if len(rows) < limit:
            try:
                rows.extend(scrape_weworkremotely_jobs(preferences, cv_text, limit=limit - len(rows)))
            except Exception:
                pass
        # de-duplicate
        unique = {}
        for item in rows:
            key = f"{(item.get('title') or '').lower()}|{(item.get('company') or '').lower()}|{(item.get('location') or '').lower()}"
            if key not in unique:
                unique[key] = item
        return list(unique.values())[:limit]
    if provider == "jsearch":
        return fetch_jsearch_jobs(preferences, cv_text, limit=limit)
    return fetch_adzuna_jobs(preferences, cv_text, limit=limit)


def compute_match_score(job: dict, cv_text: str, preferences: dict) -> dict:
    cv_tokens = tokenize(cv_text)
    job_tokens = tokenize(f"{job.get('title', '')} {job.get('description', '')} {job.get('location', '')}")
    overlap = sorted(cv_tokens & job_tokens)
    matched_skills = sorted(set(job.get("skills") or []) & cv_tokens)
    missing_skills = sorted(set(job.get("skills") or []) - cv_tokens)

    overlap_score = min(len(overlap) * 7, 55)
    skill_score = min(len(matched_skills) * 9, 35)
    preference_score = 0
    pref_reasons = []
    country = (preferences.get("country") or "").strip().lower()
    city = (preferences.get("city") or "").strip().lower()
    work_mode = (preferences.get("work_mode") or "").strip().lower()
    title = (preferences.get("job_title") or "").strip().lower()
    loc_blob = f"{job.get('location', '')} {job.get('city', '')} {job.get('country', '')}".lower()
    if country:
        if country in loc_blob:
            preference_score += 8
            pref_reasons.append(f"Country matched ({preferences.get('country')})")
        else:
            pref_reasons.append(f"Country mismatch ({preferences.get('country')})")
    if city:
        if city in loc_blob:
            preference_score += 8
            pref_reasons.append(f"City matched ({preferences.get('city')})")
        else:
            pref_reasons.append(f"City mismatch ({preferences.get('city')})")
    if work_mode:
        if work_mode == (job.get("work_mode") or "").lower():
            preference_score += 10
            pref_reasons.append(f"Work mode matched ({work_mode})")
        else:
            pref_reasons.append(f"Work mode mismatch (job is {job.get('work_mode') or 'unknown'})")
    if title:
        if title in (job.get("title") or "").lower():
            preference_score += 8
            pref_reasons.append(f"Title matched ({preferences.get('job_title')})")
        else:
            pref_reasons.append(f"Title mismatch ({preferences.get('job_title')})")

    total = min(int((overlap_score + skill_score) * 0.75 + preference_score * 0.25), 100)
    return {
        **job,
        "score": total,
        "matched_skills": matched_skills[:8],
        "missing_skills": missing_skills[:8],
        "reasons": pref_reasons[:4],
        "keyword_overlap": overlap[:8],
    }


def get_current_user_data():
    if "user_id" not in st.session_state:
        return None
    row = db_get_user(st.session_state["user_id"])
    if not row:
        st.session_state.pop("user_id", None)
        return None
    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "cv_filename": row[4],
        "cv_text": row[5] or "",
        "preferences": json.loads(row[6] or "{}"),
    }


def restore_login_from_query() -> None:
    if "user_id" in st.session_state:
        return
    token = st.query_params.get("auth", "")
    if not token:
        return
    user_id = db_get_user_id_by_token(token)
    if user_id:
        st.session_state["user_id"] = user_id


def auth_ui():
    st.sidebar.title("Smart Job Platform")
    mode = st.sidebar.radio("Session", ["Login", "Register"])
    if mode == "Register":
        with st.sidebar.form("register_form"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            try:
                db_create_user(name, email, password)
                st.sidebar.success("Account created. Please login.")
            except sqlite3.IntegrityError:
                st.sidebar.error("Email already exists.")
    else:
        with st.sidebar.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
        if submitted:
            row = db_get_user_by_email(email)
            if not row or row[3] != hash_password(password):
                st.sidebar.error("Invalid credentials")
            else:
                st.session_state["user_id"] = row[0]
                token = db_create_auth_token(row[0])
                st.query_params["auth"] = token
                st.sidebar.success("Logged in")


def main():
    st.set_page_config(page_title="Smart Job Platform - Streamlit", layout="wide")
    init_db()
    restore_login_from_query()
    auth_ui()
    user = get_current_user_data()

    st.title("Smart Job Platform (Streamlit)")
    st.caption("Simple local version with CV upload, real job fetching, and AI matching.")

    if not user:
        st.info("Please login or register from the sidebar.")
        return

    if st.sidebar.button("Logout"):
        token = st.query_params.get("auth", "")
        if token:
            db_delete_auth_token(token)
            st.query_params.clear()
        st.session_state.pop("user_id", None)
        st.rerun()

    st.sidebar.markdown(f"**Signed in as:** {user['name']}")

    default_prefs = {
        "country": user["preferences"].get("country", ""),
        "city": user["preferences"].get("city", ""),
        "work_mode": user["preferences"].get("work_mode", ""),
        "job_title": user["preferences"].get("job_title", ""),
    }

    left, right = st.columns([1, 1.4])
    with left:
        st.subheader("Profile & Preferences")
        with st.form("preferences_form"):
            country = st.text_input("Preferred country", value=default_prefs["country"])
            city = st.text_input("Preferred city", value=default_prefs["city"])
            work_mode = st.selectbox("Work mode", ["", "remote", "hybrid", "on-site"], index=["", "remote", "hybrid", "on-site"].index(default_prefs["work_mode"]) if default_prefs["work_mode"] in ["", "remote", "hybrid", "on-site"] else 0)
            job_title = st.text_input("Preferred job title", value=default_prefs["job_title"])
            save_prefs = st.form_submit_button("Save preferences")
        if save_prefs:
            prefs = {"country": country, "city": city, "work_mode": work_mode, "job_title": job_title}
            db_update_preferences(user["id"], prefs)
            st.success("Preferences saved.")
            user = get_current_user_data()

        st.subheader("CV Upload")
        uploaded = st.file_uploader("Upload CV (.txt, .pdf)", type=["txt", "pdf"])
        if st.button("Save CV"):
            if not uploaded:
                st.warning("Please select a CV file first.")
            else:
                text = parse_uploaded_cv(uploaded)
                if len(text.strip()) < 20:
                    st.error("CV content is too short.")
                else:
                    db_update_cv(user["id"], uploaded.name, text.strip())
                    st.success("CV uploaded and saved.")
                    user = get_current_user_data()
        st.write(f"CV saved: {'Yes' if user['cv_text'].strip() else 'No'}")
        if user["cv_filename"]:
            st.write(f"CV file: `{user['cv_filename']}`")

    with right:
        st.subheader("Dashboard Summary")
        if "last_jobs" not in st.session_state:
            st.session_state["last_jobs"] = []
        if "last_matches" not in st.session_state:
            st.session_state["last_matches"] = []

        prefs = user["preferences"] if user["preferences"] else default_prefs
        fetch_col, count_col = st.columns([1, 1])
        with fetch_col:
            fetch_clicked = st.button("Fetch Jobs")
        with count_col:
            limit = st.number_input("Jobs to fetch", min_value=5, max_value=50, value=20, step=5)

        if fetch_clicked:
            with st.spinner("Fetching jobs and computing matches..."):
                cv_text = user["cv_text"] or ""
                jobs = fetch_real_jobs(prefs, cv_text, limit=int(limit))
                matches = [compute_match_score(job, cv_text, prefs) for job in jobs]
                matches.sort(key=lambda x: x["score"], reverse=True)
                st.session_state["last_jobs"] = jobs
                st.session_state["last_matches"] = matches
            if not jobs:
                st.warning("No jobs returned right now. Try broader job title or city, then click Fetch Jobs again.")

        jobs = st.session_state["last_jobs"]
        matches = st.session_state["last_matches"]
        top_score = matches[0]["score"] if matches else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Fetched jobs", len(jobs))
        c2.metric("Recommendations", len(matches))
        c3.metric("Top match score", f"{top_score}%")

        st.subheader("Job Recommendations")
        if not matches:
            st.info("Fetch jobs to see recommendations.")
        for item in matches[:10]:
            st.markdown(f"### {item['title']}")
            st.write(f"{item['company']} | {item['location']} | {item.get('work_mode') or 'unknown'}")
            st.write(f"Match score: **{item['score']}%**")
            if item.get("apply_url"):
                st.markdown(f"[Apply here]({item['apply_url']})")
            if item["matched_skills"]:
                st.write("Matched skills:", ", ".join(item["matched_skills"]))
            if item["missing_skills"]:
                st.write("Missing skills:", ", ".join(item["missing_skills"]))
            if item["reasons"]:
                st.write("Preference reasons:", " | ".join(item["reasons"]))
            st.divider()


if __name__ == "__main__":
    main()
