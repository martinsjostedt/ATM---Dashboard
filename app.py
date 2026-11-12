"""ATM Dashboard – Jenny Lind | Artist Booking & Tour Management."""
import os

import psycopg
from psycopg.rows import dict_row
import streamlit as st

st.set_page_config(page_title="ATM | Jenny Lind", page_icon="🎼", layout="wide")

COLUMN_LABELS = {
    "kontakt_id": "Kontakt-ID",
    "fornamn": "Förnamn",
    "efternamn": "Efternamn",
    "organisation": "Organisation",
    "kategori": "Kategori",
    "roll": "Roll",
    "epostadress": "E-post",
    "telefonnummer": "Telefon",
    "stad": "Ort",
    "land": "Land",
    "stift": "Stift",
    "hemsida": "Hemsida",
    "kommentar": "Kommentar",
    "evenemang_start": "Evenemang start",
    "evenemang_slut": "Evenemang slut",
    "import": "Import",
    "skapad_at": "Skapad",
}
CONTACT_COLUMNS = tuple(COLUMN_LABELS)


def get_database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:
        return st.secrets.get("DATABASE_URL")
    except (FileNotFoundError, KeyError):
        return None


@st.cache_data(ttl=60, show_spinner="Hämtar kontakter från Neon…")
def load_contacts(_database_url):
    """Read only: never modify the production contacts table."""
    sql = """
        SELECT kontakt_id, fornamn, efternamn, organisation, kategori,
               roll, epostadress, telefonnummer, stad, land, stift,
               hemsida, kommentar, evenemang_start, evenemang_slut,
               import, skapad_at
          FROM public.kontakter
         ORDER BY organisation NULLS LAST, efternamn NULLS LAST,
                  fornamn NULLS LAST, kontakt_id
    """
    with psycopg.connect(_database_url, connect_timeout=8, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


def display(value):
    return "" if value is None else str(value)


def contact_name(contact):
    return " ".join(
        display(contact.get(key)).strip()
        for key in ("fornamn", "efternamn")
        if display(contact.get(key)).strip()
    )


st.title("Jenny Lind")
st.caption("Artist Booking & Tour Management · ATM")

with st.sidebar:
    st.header("ATM")
    page = st.radio(
        "Navigering",
        ["Översikt", "Kontakter", "Projekt", "Fakturor", "Kampanjer"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Version 0.3 · Kontakter (läsning)")

database_url = get_database_url()

if page == "Översikt":
    st.subheader("Översikt")
    st.write("Välkommen till ATM Dashboard. Här samlar vi artistbokning, turnéer, kontakter och fakturering.")
    if not database_url:
        st.warning("DATABASE_URL saknas. Ange den i Streamlit Community Cloud → App settings → Secrets.")
    else:
        try:
            contacts = load_contacts(database_url)
            first, second, third = st.columns(3)
            first.metric("Kontakter", f"{len(contacts):,}".replace(",", " "))
            second.metric("Aktiva projekt", "–")
            third.metric("Obetalda fakturor", "–")
            st.success("Neon PostgreSQL svarar.")
        except psycopg.Error:
            st.error("Neon kunde inte nås. Kontrollera DATABASE_URL i Streamlit Secrets.")
    st.info("Projekt och fakturor kopplas in i kommande versioner.")

elif page == "Kontakter":
    st.subheader("Kontakter")
    st.caption("Huvudregistret i Neon · public.kontakter · endast läsning")
    if not database_url:
        st.warning("Ange DATABASE_URL under Streamlit App settings → Secrets för att visa kontakter.")
        st.stop()
    try:
        contacts = load_contacts(database_url)
    except psycopg.Error:
        st.error("Kunde inte läsa kontaktregistret från Neon. Kontrollera anslutningen.")
        st.stop()

    search_col, cat_col, city_col = st.columns([2, 1, 1])
    with search_col:
        search = st.text_input("Sök", placeholder="Namn, organisation, e-post, ort …")
    categories = sorted({display(c["kategori"]).strip() for c in contacts if c.get("kategori")})
    cities = sorted({display(c["stad"]).strip() for c in contacts if c.get("stad")})
    with cat_col:
        selected_categories = st.multiselect("Kategori", categories)
    with city_col:
        selected_cities = st.multiselect("Ort", cities)

    terms = search.casefold().strip().split()
    searchable_fields = ("fornamn", "efternamn", "organisation", "epostadress",
                         "stad", "land", "kategori", "roll", "stift", "telefonnummer")
    filtered = [
        c for c in contacts
        if (not selected_categories or display(c.get("kategori")).strip() in selected_categories)
        and (not selected_cities or display(c.get("stad")).strip() in selected_cities)
        and all(term in " ".join(display(c.get(k)) for k in searchable_fields).casefold() for term in terms)
    ]

    top_left, top_right = st.columns([3, 1])
    top_left.metric("Visade kontakter", f"{len(filtered):,}".replace(",", " "))
    with top_right:
        if st.button("Uppdatera från Neon", use_container_width=True):
            load_contacts.clear()
            st.rerun()

    shown = ("kontakt_id", "fornamn", "efternamn", "organisation", "kategori",
             "roll", "epostadress", "telefonnummer", "stad", "land")
    st.dataframe(
        [{COLUMN_LABELS[key]: display(c.get(key)) for key in shown} for c in filtered],
        hide_index=True,
        use_container_width=True,
        height=440,
    )

    if filtered:
        st.divider()
        st.markdown("#### Kontaktinformation")
        selected_id = st.selectbox(
            "Välj kontakt",
            [c["kontakt_id"] for c in filtered],
            format_func=lambda cid: next(
                (f"{contact_name(c) or c.get('organisation') or 'Namnlös'}"
                 f" · {c.get('organisation') or 'Ingen organisation'} · ID {cid}"
                 for c in filtered if c["kontakt_id"] == cid), str(cid)
            ),
        )
        selected = next(c for c in filtered if c["kontakt_id"] == selected_id)
        left, right = st.columns(2)
        fields = [key for key in CONTACT_COLUMNS if key not in ("skapad_at", "import")]
        for index, key in enumerate(fields):
            target = left if index % 2 == 0 else right
            with target:
                st.text_input(COLUMN_LABELS[key], value=display(selected.get(key)), disabled=True,
                              key=f"detail_{key}_{selected_id}")
        if selected.get("skapad_at"):
            st.caption(f"Registrerad: {selected['skapad_at']}")
    else:
        st.info("Inga kontakter matchar filtren.")

else:
    st.subheader(page)
    st.info(f"Vyn {page.lower()} är förberedd. Funktioner mot Neon kommer senare.")

st.divider()
st.caption("ATM · Jenny Lind | Artist Booking & Tour Management")
