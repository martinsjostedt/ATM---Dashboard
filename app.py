"""ATM Dashboard – initial Cloud Run-ready Streamlit application."""
import os

import streamlit as st

st.set_page_config(page_title="ATM | Jenny Lind", page_icon="🎼", layout="wide")

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
    st.caption("Version 0.1 · Första driftsättning")

if page == "Översikt":
    st.subheader("Översikt")
    st.write("Välkommen till ATM Dashboard. Här samlar vi artistbokning, turnéer, kontakter och fakturering.")
    col1, col2, col3 = st.columns(3)
    col1.metric("Kontakter", "–")
    col2.metric("Aktiva projekt", "–")
    col3.metric("Obetalda fakturor", "–")
    st.info("Nyckeltal visas när respektive vy har kopplats till Neon.")

    st.subheader("Databasanslutning")
    if not os.getenv("DATABASE_URL"):
        st.warning("DATABASE_URL saknas. Lägg till anslutningen som en hemlighet i Cloud Run – aldrig i GitHub.")
    else:
        try:
            import psycopg
            with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            st.success("Neon PostgreSQL svarar.")
        except Exception:
            st.error("Databasen kunde inte nås. Kontrollera Cloud Runs DATABASE_URL och nätverksinställningar.")
else:
    st.subheader(page)
    st.info(f"Vyn {page.lower()} är förberedd. Här lägger vi snart in funktioner mot Neon.")

st.divider()
st.caption("ATM · Jenny Lind | Artist Booking & Tour Management")
