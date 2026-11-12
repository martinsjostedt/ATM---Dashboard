"""ATM – dynamiska, manuellt redigerbara utskickslistor."""
import os
import hmac
import json

import psycopg
from psycopg.rows import dict_row
import streamlit as st

st.set_page_config(page_title="Utskickslistor | ATM", page_icon="📨", layout="wide")
st.title("Utskickslistor")
st.caption("Dynamiska kontakturval med manuella tillägg och undantag · Neon")


def secret(name):
    if os.getenv(name):
        return os.environ[name]
    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None


def authorized():
    password_secret = secret("ATM_DASHBOARD_PASSWORD")
    if not password_secret:
        st.error("Utskickslistor är låsta. Ange ATM_DASHBOARD_PASSWORD i Streamlit Secrets.")
        return False
    if st.session_state.get("invoice_authorized") or st.session_state.get("lists_authorized"):
        return True
    with st.form("lists_login"):
        entered = st.text_input("ATM-lösenord", type="password")
        ok = st.form_submit_button("Öppna utskickslistor")
    if ok:
        if hmac.compare_digest(entered, password_secret):
            st.session_state["lists_authorized"] = True
            st.rerun()
        st.error("Fel lösenord.")
    return False


if not authorized():
    st.stop()

DATABASE_URL = secret("DATABASE_URL")
if not DATABASE_URL:
    st.error("DATABASE_URL saknas i Streamlit Secrets.")
    st.stop()


def fetch(sql, params=()):
    with psycopg.connect(DATABASE_URL, connect_timeout=8, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql, params=(), returning=False):
    with psycopg.connect(DATABASE_URL, connect_timeout=8, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if returning:
                return cur.fetchone()


def nice_contact(c):
    name = " ".join(str(c[k]).strip() for k in ("fornamn", "efternamn") if c.get(k))
    return f"{c['kontakt_id']} · {c.get('organisation') or name or 'Namnlös'} · {c.get('epostadress') or 'saknar e-post'}"


try:
    lists = fetch("SELECT * FROM public.utskickslistor ORDER BY namn")
    categories = fetch("""
        SELECT DISTINCT kategori FROM (
          SELECT kategori_1 AS kategori FROM public.kontakter
          UNION ALL SELECT kategori_2 FROM public.kontakter
        ) x WHERE kategori IS NOT NULL AND btrim(kategori) <> ''
        ORDER BY kategori
    """)
    lands = fetch("SELECT DISTINCT land FROM public.kontakter WHERE nullif(btrim(land),'') IS NOT NULL ORDER BY land")
    contacts = fetch("""
        SELECT kontakt_id, fornamn, efternamn, organisation, epostadress, kategori_1, kategori_2, ort, land
        FROM public.kontakter ORDER BY organisation NULLS LAST, efternamn NULLS LAST, kontakt_id
    """)
except psycopg.Error as exc:
    st.error(f"Kunde inte läsa data från Neon: {exc}")
    st.stop()

tab_lists, tab_campaigns = st.tabs(["Utskickslistor", "Kampanjer"])

with tab_lists:
    with st.expander("Skapa ny dynamisk lista"):
        with st.form("new_list"):
            new_name = st.text_input("Namn på listan")
            new_description = st.text_input("Beskrivning")
            col_a, col_b = st.columns(2)
            new_cat = col_a.selectbox("Kategori", ["Alla"] + [x["kategori"] for x in categories], key="new_cat")
            new_land = col_b.selectbox("Land", ["Alla"] + [x["land"] for x in lands], key="new_land")
            new_use_second = st.checkbox("Sök även i Kategori 2", value=True, key="new_second")
            new_billing = st.selectbox("Faktureringskontakt", ["Alla", "Ja", "Nej"], key="new_billing")
            create = st.form_submit_button("Skapa lista", type="primary")
        if create:
            if not new_name.strip():
                st.warning("Ange ett namn.")
            else:
                rules = {"inkludera_kategori_2": new_use_second}
                if new_cat != "Alla":
                    rules["kategori"] = new_cat
                if new_land != "Alla":
                    rules["land"] = new_land
                if new_billing != "Alla":
                    rules["faktureringskontakt"] = new_billing == "Ja"
                try:
                    execute("""INSERT INTO public.utskickslistor(namn,beskrivning,filterregler)
                               VALUES(%s,%s,%s::jsonb)""",
                            (new_name.strip(),new_description.strip(),json.dumps(rules)))
                    st.success("Listan har skapats.")
                    st.rerun()
                except psycopg.errors.UniqueViolation:
                    st.error("En lista med det namnet finns redan.")
                except psycopg.Error as exc:
                    st.error(f"Kunde inte skapa listan: {exc}")

    if not lists:
        st.info("Skapa den första listan ovan.")
    else:
        chosen = st.selectbox("Välj utskickslista", lists, format_func=lambda x: x["namn"])
        list_id = chosen["id"]
        rules = chosen["filterregler"]
        if isinstance(rules, str):
            rules = json.loads(rules)

        with st.expander("Redigera listans filter", expanded=False):
            with st.form(f"edit_filters_{list_id}"):
                name = st.text_input("Listnamn", value=chosen["namn"])
                description = st.text_input("Beskrivning", value=chosen["beskrivning"] or "")
                cat_options = ["Alla"] + [x["kategori"] for x in categories]
                land_options = ["Alla"] + [x["land"] for x in lands]
                cat = st.selectbox("Kategori", cat_options, index=cat_options.index(rules.get("kategori", "Alla")) if rules.get("kategori", "Alla") in cat_options else 0)
                land = st.selectbox("Land", land_options, index=land_options.index(rules.get("land", "Alla")) if rules.get("land", "Alla") in land_options else 0)
                second = st.checkbox("Inkludera Kategori 2", value=rules.get("inkludera_kategori_2", True))
                billing_value = rules.get("faktureringskontakt")
                billing_options = ["Alla", "Ja", "Nej"]
                billing = st.selectbox("Faktureringskontakt", billing_options, index=0 if billing_value is None else (1 if billing_value else 2))
                save = st.form_submit_button("Spara filter")
            if save:
                new_rules = {"inkludera_kategori_2": second}
                if cat != "Alla":
                    new_rules["kategori"] = cat
                if land != "Alla":
                    new_rules["land"] = land
                if billing != "Alla":
                    new_rules["faktureringskontakt"] = billing == "Ja"
                try:
                    execute("""UPDATE public.utskickslistor SET namn=%s,beskrivning=%s,
                               filterregler=%s::jsonb,uppdaterad_at=now() WHERE id=%s""",
                            (name.strip(), description.strip(),json.dumps(new_rules),list_id))
                    st.success("Filtret har uppdaterats.")
                    st.rerun()
                except psycopg.Error as exc:
                    st.error(f"Kunde inte spara: {exc}")

        try:
            members = fetch("SELECT * FROM public.utskickslista_mottagare(%s)", (list_id,))
            overrides = fetch("""
                SELECT a.kontakt_id,a.atgard,k.organisation,k.fornamn,k.efternamn,k.epostadress
                FROM public.utskickslista_undantag a
                JOIN public.kontakter k ON k.kontakt_id=a.kontakt_id
                WHERE a.lista_id=%s ORDER BY a.atgard,k.organisation
            """, (list_id,))
        except psycopg.Error as exc:
            st.error(f"Kunde inte läsa mottagare: {exc}")
            st.stop()

        a,b,c = st.columns(3)
        a.metric("Mottagare med e-post",len(members))
        b.metric("Manuella tillägg",sum(x["atgard"]=="inkludera" for x in overrides))
        c.metric("Manuella undantag",sum(x["atgard"]=="exkludera" for x in overrides))
        st.caption("Nya kontakter som uppfyller filtret tillkommer automatiskt. Manuella ändringar består.")
        search = st.text_input("Sök i mottagarlistan", key=f"member_search_{list_id}")
        filtered_members = [
            m for m in members
            if search.casefold() in (" ".join(str(v or "") for v in m.values())).casefold()
        ]
        st.dataframe([
            {"Kontakt-ID": m["kontakt_id"],
             "Namn": " ".join(str(m[x]) for x in ("fornamn","efternamn") if m[x]),
             "Organisation":m["organisation"],"E-post":m["epostadress"],
             "Ort":m["ort"],"Urval":m["urvalstyp"]}
            for m in filtered_members
        ], hide_index=True, use_container_width=True, height=380)

        st.markdown("#### Ändra en kontakt manuellt")
        find_contact = st.text_input("Sök kontakt i hela registret", placeholder="Namn, organisation eller e-post", key=f"search_all_{list_id}")
        matching = [
            x for x in contacts
            if find_contact.strip() and find_contact.casefold() in
            nice_contact(x).casefold()
        ][:100]
        if matching:
            with st.form(f"override_{list_id}"):
                target = st.selectbox("Kontakt",matching,format_func=nice_contact)
                action = st.radio("Åtgärd",["Lägg till","Uteslut","Återgå till dynamiskt urval"],horizontal=True)
                submit = st.form_submit_button("Spara ändring", type="primary")
            if submit:
                try:
                    if action=="Återgå till dynamiskt urval":
                        execute("DELETE FROM public.utskickslista_undantag WHERE lista_id=%s AND kontakt_id=%s",(list_id,target["kontakt_id"]))
                    else:
                        mode = "inkludera" if action=="Lägg till" else "exkludera"
                        execute("""INSERT INTO public.utskickslista_undantag(lista_id,kontakt_id,atgard)
                                   VALUES(%s,%s,%s) ON CONFLICT(lista_id,kontakt_id)
                                   DO UPDATE SET atgard=EXCLUDED.atgard""",(list_id,target["kontakt_id"],mode))
                    st.success("Ändringen har sparats.")
                    st.rerun()
                except psycopg.Error as exc:
                    st.error(f"Ändringen kunde inte sparas: {exc}")
        elif find_contact.strip():
            st.info("Ingen kontakt hittades.")

        if overrides:
            st.markdown("#### Sparade manuella ändringar")
            st.dataframe([{
                "Kontakt-ID":x["kontakt_id"],"Organisation":x["organisation"],
                "E-post":x["epostadress"],"Åtgärd":x["atgard"]
            } for x in overrides],hide_index=True,use_container_width=True)

with tab_campaigns:
    try:
        projects = fetch("SELECT id,namn FROM public.projekt ORDER BY namn")
        campaigns = fetch("SELECT * FROM public.kampanjer ORDER BY namn")
    except psycopg.Error as exc:
        st.error(f"Kan inte läsa kampanjer: {exc}")
        st.stop()

    with st.expander("Skapa kampanj"):
        with st.form("new_campaign"):
            campaign_name = st.text_input("Kampanjnamn")
            project = st.selectbox("Projekt", [None]+projects,format_func=lambda x: "Inget projekt" if x is None else x["namn"])
            campaign_description = st.text_input("Beskrivning")
            create_campaign = st.form_submit_button("Skapa kampanj", type="primary")
        if create_campaign:
            if campaign_name.strip():
                try:
                    execute("""INSERT INTO public.kampanjer(namn,projekt_id,beskrivning)
                               VALUES(%s,%s,%s)""",
                            (campaign_name.strip(),project["id"] if project else None,campaign_description))
                    st.success("Kampanjen har skapats.")
                    st.rerun()
                except psycopg.Error as exc:
                    st.error(f"Det gick inte att skapa kampanjen: {exc}")
            else:
                st.warning("Ange ett kampanjnamn.")

    if campaigns:
        campaign = st.selectbox("Välj kampanj",campaigns,format_func=lambda x:x["namn"])
        linked = fetch("SELECT lista_id FROM public.kampanj_utskickslistor WHERE kampanj_id=%s",(campaign["id"],))
        selected_ids = {x["lista_id"] for x in linked}
        with st.form(f"campaign_lists_{campaign['id']}"):
            chosen_lists = st.multiselect("Kopplade utskickslistor",lists,
                default=[l for l in lists if l["id"] in selected_ids],
                format_func=lambda l:l["namn"])
            save_links = st.form_submit_button("Spara listkopplingar")
        if save_links:
            try:
                with psycopg.connect(DATABASE_URL,connect_timeout=8) as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM public.kampanj_utskickslistor WHERE kampanj_id=%s",(campaign["id"],))
                        for l in chosen_lists:
                            cur.execute("INSERT INTO public.kampanj_utskickslistor(kampanj_id,lista_id) VALUES(%s,%s)",(campaign["id"],l["id"]))
                st.success("Kampanjens listor har sparats.")
                st.rerun()
            except psycopg.Error as exc:
                st.error(f"Kunde inte spara kopplingar: {exc}")
        st.caption("Utskicksutkast fryser mottagare och e-postadresser. Inga e-postmeddelanden skickas här.")
        if st.button("Skapa mottagarögonblicksbild", type="secondary"):
            try:
                with psycopg.connect(DATABASE_URL,connect_timeout=8,row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO public.kampanjutskick(kampanj_id) VALUES(%s) RETURNING id",(campaign["id"],))
                        batch_id = cur.fetchone()["id"]
                        cur.execute("""
                            INSERT INTO public.kampanjutskick_mottagare
                              (utskick_id,kontakt_id,epostadress,namn,organisation)
                            SELECT %s,m.kontakt_id,m.epostadress,
                                concat_ws(' ',m.fornamn,m.efternamn),m.organisation
                            FROM public.kampanj_utskickslistor kl
                            CROSS JOIN LATERAL public.utskickslista_mottagare(kl.lista_id) m
                            WHERE kl.kampanj_id=%s
                            ON CONFLICT(utskick_id,epostadress) DO NOTHING
                        """,(batch_id,campaign["id"]))
                        saved = cur.rowcount
                st.success(f"Utkast #{batch_id} skapat med {saved} mottagare. Inga mejl har skickats.")
            except psycopg.Error as exc:
                st.error(f"Kunde inte skapa utkast: {exc}")
        batches = fetch("""SELECT u.id,u.skapad_at,u.status,count(m.epostadress) antal
             FROM public.kampanjutskick u LEFT JOIN public.kampanjutskick_mottagare m ON m.utskick_id=u.id
             WHERE u.kampanj_id=%s GROUP BY u.id ORDER BY u.id DESC""",(campaign["id"],))
        if batches:
            st.dataframe(batches,hide_index=True,use_container_width=True)
