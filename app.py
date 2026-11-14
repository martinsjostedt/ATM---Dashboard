"""ATM Dashboard – Jenny Lind | Artist Booking & Tour Management."""
import os
import hmac
import re

import psycopg
from psycopg.rows import dict_row
import streamlit as st
from campaign_gmail import export_gmail_draft, fetch_neon_image

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



@st.cache_data(ttl=60, show_spinner="Hämtar fakturor från Neon…")
def load_invoices(_database_url):
    """Read invoice headers without changing any accounting records."""
    with psycopg.connect(_database_url, connect_timeout=8, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, fakturanummer, mottagare_namn, totalbelopp, valuta, status,
                       fakturadatum
                  FROM public.fakturor
                 ORDER BY fakturadatum DESC NULLS LAST, id DESC
            """)
            return cur.fetchall()


@st.cache_data(ttl=60, show_spinner="Hämtar fakturadetaljer…")
def load_invoice_detail(_database_url, invoice_id):
    """Fetch the exact stored invoice and its associated invoice lines."""
    with psycopg.connect(_database_url, connect_timeout=8, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM public.fakturor WHERE id = %s", (invoice_id,))
            invoice = cur.fetchone()
            if invoice is None:
                return None, []
            cur.execute("""
                SELECT * FROM public.fakturarader
                 WHERE faktura_id = %s
                 ORDER BY sortering, id
            """, (invoice_id,))
            lines = cur.fetchall()
            return invoice, lines


def secret_value(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None


def invoice_access_allowed():
    """Block invoice information unless a server-side access password is configured."""
    secret = secret_value("ATM_DASHBOARD_PASSWORD")
    if not secret:
        st.error("Fakturavyn är låst tills ATM_DASHBOARD_PASSWORD har lagts in i Streamlit Secrets.")
        st.caption("Lägg in ett starkt lösenord i Streamlit → App settings → Secrets. Lagra aldrig lösenordet i GitHub.")
        return False
    if st.session_state.get("invoice_authorized") is True:
        return True
    with st.form("invoice_login"):
        password = st.text_input("Lösenord för fakturor", type="password")
        submitted = st.form_submit_button("Öppna fakturor")
    if submitted:
        if hmac.compare_digest(password, secret):
            st.session_state["invoice_authorized"] = True
            st.rerun()
        else:
            st.error("Fel lösenord.")
    return False


def invoice_field_label(field):
    overrides = {
        "id": "Databas-ID", "fakturanummer": "Fakturanummer",
        "mottagare_namn": "Mottagare namn", "totalbelopp": "Summa",
        "netto": "Netto", "momsbelopp": "Momsbelopp",
        "status": "Status", "valuta": "Valuta",
    }
    return overrides.get(field, field.replace("_", " ").capitalize())


def invoice_details_fields(invoice, fields):
    """Show each stored invoice field, including nulls, as a read-only value."""
    for field in fields:
        st.text_input(
            invoice_field_label(field),
            value=display(invoice.get(field)) or "—",
            disabled=True,
            key=f"invoice_{invoice['id']}_{field}",
        )


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
    pages = ["Översikt", "Kontakter", "Projekt", "Fakturor", "Kampanjer", "Kampanjmejl"]
    page = st.radio(
        "Navigering",
        pages,
        index=3 if st.query_params.get("faktura_id") else 0,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Version 0.4 · Kontakter och fakturor (läsning)")

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


elif page == "Fakturor":
    st.subheader("Fakturor")
    st.caption("Neon · public.fakturor · endast läsning")
    if not invoice_access_allowed():
        st.stop()
    if not database_url:
        st.error("DATABASE_URL saknas. Lägg in anslutningen i Streamlit Secrets.")
        st.stop()

    selected_param = st.query_params.get("faktura_id")
    if selected_param:
        try:
            selected_id = int(selected_param)
            if selected_id <= 0:
                raise ValueError("Invalid id")
        except (ValueError, TypeError):
            st.error("Ogiltigt faktura-ID.")
            if st.button("Till fakturalistan"):
                del st.query_params["faktura_id"]
                st.rerun()
            st.stop()
        if st.button("← Till alla fakturor"):
            del st.query_params["faktura_id"]
            st.rerun()
        try:
            invoice, invoice_lines = load_invoice_detail(database_url, selected_id)
        except psycopg.Error:
            st.error("Fakturan kunde inte hämtas från Neon.")
            st.stop()
        if not invoice:
            st.warning("Fakturan finns inte.")
            st.stop()

        st.markdown(f"### Faktura {display(invoice.get('fakturanummer')) or selected_id}")
        st.caption(f"{display(invoice.get('mottagare_namn'))} · {display(invoice.get('status'))}")
        groups = [
            ("Fakturauppgifter", ["id", "fakturanummer", "fakturadatum", "forfallodatum",
                "betalningsvillkor_dagar", "status", "valuta", "sprak", "projekt_id",
                "var_referens", "er_referens", "drojsmalsvillkor", "betalningsreferens",
                "skickad_datum", "betald_datum", "inbetalt_belopp"]),
            ("Mottagare", [k for k in invoice if k.startswith("mottagare_")]),
            ("Avsändare", [k for k in invoice if k.startswith("avsandare_")]),
            ("Belopp", ["netto", "momsbelopp", "oresutjamning", "totalbelopp"]),
            ("Texter och metadata", ["fakturatext", "intern_anteckning", "skapad_at",
                "uppdaterad_at"]),
        ]
        seen = set()
        for heading, fields in groups:
            fields = [field for field in fields if field in invoice]
            seen.update(fields)
            with st.expander(heading, expanded=(heading == "Fakturauppgifter")):
                left, right = st.columns(2)
                for n, field in enumerate(fields):
                    with (left if n % 2 == 0 else right):
                        invoice_details_fields(invoice, [field])
        remaining = [key for key in invoice if key not in seen]
        if remaining:
            with st.expander("Övriga fakturafält"):
                invoice_details_fields(invoice, remaining)

        st.markdown("#### Fakturarader")
        if invoice_lines:
            st.dataframe(
                [{k: display(v) for k, v in line.items()} for line in invoice_lines],
                hide_index=True, use_container_width=True,
            )
        else:
            st.info("Inga fakturarader finns registrerade på denna faktura.")

    else:
        try:
            invoices = load_invoices(database_url)
        except psycopg.Error:
            st.error("Fakturorna kunde inte hämtas från Neon.")
            st.stop()
        controls, count = st.columns([3, 1])
        with controls:
            query = st.text_input("Sök faktura", placeholder="Fakturanummer, mottagare eller status")
        with count:
            if st.button("Uppdatera", use_container_width=True):
                load_invoices.clear()
                load_invoice_detail.clear()
                st.rerun()
        terms = query.strip().casefold().split()
        filtered_invoices = [
            inv for inv in invoices
            if all(term in " ".join(display(inv.get(k)) for k in
               ("fakturanummer", "mottagare_namn", "status")).casefold()
               for term in terms)
        ]
        st.caption(f"{len(filtered_invoices)} av {len(invoices)} fakturor")
        rows = []
        for inv in filtered_invoices:
            amount = inv.get("totalbelopp")
            money = (f"{amount:,.2f}".replace(",", " ").replace(".", ",")
                     if amount is not None else "—")
            currency = display(inv.get("valuta")).strip()
            rows.append({
                "Fakturanummer": display(inv.get("fakturanummer")) or "—",
                "Mottagare_namn": display(inv.get("mottagare_namn")) or "—",
                "Summa": money + (f" {currency}" if amount is not None and currency else ""),
                "Status": display(inv.get("status")) or "—",
                "Detaljer": f"https://atmdash.streamlit.app/?faktura_id={inv['id']}",
            })
        st.dataframe(
            rows, hide_index=True, use_container_width=True, height=520,
            column_config={
                "Detaljer": st.column_config.LinkColumn(
                    "Visa faktura", display_text="Öppna →"
                )
            },
        )
        if not invoices:
            st.info("Inga fakturor finns i Neon ännu.")


elif page == "Kampanjmejl":
    st.subheader("Kampanjmejl → Gmail")
    st.caption("Exportera som utkast med bild inuti mejlet och som nedladdningsbar bilaga.")
    if not invoice_access_allowed():
        st.stop()
    if not database_url:
        st.error("DATABASE_URL saknas.")
        st.stop()
    try:
        with psycopg.connect(database_url, connect_timeout=8, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.id, m.namn, m.amne, m.meddelande, m.bilaga_1,
                           m.bilaga_2, m.bilaga_3, k.namn AS kampanj
                    FROM public.kampanjmejl m
                    LEFT JOIN public.kampanjer k ON k.id = m.kampanj_id
                    ORDER BY m.id DESC
                """)
                campaign_emails = cur.fetchall()
    except psycopg.Error:
        st.error("Kunde inte hämta kampanjmejl från Neon.")
        st.stop()
    if not campaign_emails:
        st.info("Inga kampanjmejl hittades.")
        st.stop()
    chosen_id = st.selectbox(
        "Välj kampanjmejl",
        [x["id"] for x in campaign_emails],
        format_func=lambda mid: next(
            f"{x['kampanj'] or 'Ingen kampanj'} – {x['namn']} (#{mid})"
            for x in campaign_emails if x["id"] == mid
        ),
    )
    chosen = next(x for x in campaign_emails if x["id"] == chosen_id)
    st.write("**Ämne:**", chosen["amne"])
    st.write("**Bildfiler:**", ", ".join(
        x.split("/")[-1] for x in (chosen["bilaga_1"], chosen["bilaga_2"], chosen["bilaga_3"]) if x
    ) or "Inga")
    st.text_area("Mejlets källtext (förhandsvisning)", chosen["meddelande"] or "", height=240, disabled=True)
    recipient = st.text_input("Mottagarens e-postadress", placeholder="namn@festival.se")
    required = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN",
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_ENDPOINT_URL_S3")
    missing = [name for name in required if not secret_value(name)]
    if missing:
        st.warning("För att aktivera exporten, konfigurera Streamlit Secrets: " + ", ".join(missing))
    if st.button("Skapa Gmail-utkast med bilder", disabled=bool(missing) or not recipient):
        try:
            settings = {name: secret_value(name) for name in required}
            settings["AWS_REGION"] = secret_value("AWS_REGION") or "us-east-2"
            image_keys = [chosen[f"bilaga_{i}"] for i in range(1, 4) if chosen[f"bilaga_{i}"]]
            placeholders = re.findall(r'<img\b[^>]*src=["\']cid:([^"\']+)["\']', chosen["meddelande"] or "", re.I)
            if len(placeholders) > len(image_keys):
                raise ValueError("Fler inbäddade bildmarkörer än tillgängliga bildfiler.")
            if image_keys and not placeholders:
                raise ValueError("Bildfil finns men ingen CID-bildmarkör i mejlet.")
            images = {}
            for cid, key in zip(placeholders, image_keys):
                images[cid] = fetch_neon_image(key, settings)
            if len(images) != len(placeholders):
                raise ValueError("Dubblerade CID-markörer. Varje bild behöver ett unikt CID.")
            draft_id = export_gmail_draft(
                chosen["amne"], chosen["meddelande"] or "", recipient, images, settings
            )
            st.success("Gmail-utkast skapat. Ingenting har skickats.")
            st.link_button("Öppna Gmail-utkast", f"https://mail.google.com/mail/u/0/#drafts?compose={draft_id}")
        except Exception as exc:
            st.error("Exporten misslyckades. Kontrollera Neon/Gmail-konfiguration och bildreferenser.")
            st.caption(f"Feltyp: {type(exc).__name__}")

else:
    st.subheader(page)
    st.info(f"Vyn {page.lower()} är förberedd. Funktioner mot Neon kommer senare.")

st.divider()
st.caption("ATM · Jenny Lind | Artist Booking & Tour Management")
