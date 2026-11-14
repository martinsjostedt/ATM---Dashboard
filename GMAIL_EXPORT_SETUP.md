# ATM – Gmail export av kampanjmejl

Den nya sidan **Kampanjmejl** skapar endast utkast. Inga mejl skickas.

## Säkerhetskrav
Dashboarden kräver `ATM_DASHBOARD_PASSWORD` innan kampanjmejl får läsas eller exporteras. För produktionsbruk bör detta ersättas med användarspecifik inloggning. Lägg aldrig in nycklar i GitHub.

## Streamlit Secrets
Konfigurera följande i Streamlit → App settings → Secrets:

```toml
DATABASE_URL = "..."
ATM_DASHBOARD_PASSWORD = "..."
AWS_ENDPOINT_URL_S3 = "https://br-shy-field-bera3p8o.storage.c-9.us-east-2.aws.neon.tech"
AWS_REGION = "us-east-2"
AWS_ACCESS_KEY_ID = "..."
AWS_SECRET_ACCESS_KEY = "..."
GMAIL_CLIENT_ID = "..."
GMAIL_CLIENT_SECRET = "..."
GMAIL_REFRESH_TOKEN = "..."
```

**Neon:** Skapa en branch-scoped credential med enbart `storage:read` i Neon → Credentials. Kopiera credential token ID till `AWS_ACCESS_KEY_ID` och S3 secret access key till `AWS_SECRET_ACCESS_KEY`. Bucket `uploads` är privat.

**Google:** Skapa en Google Cloud OAuth Client för ett Gmail-konto. Aktivera Gmail API. Genomför en engångs-OAuth-inloggning med scopet `https://www.googleapis.com/auth/gmail.compose` och offline access och spara refresh token i Secrets. OAuth consent screen och eventuell test-user access måste vara korrekt inställd. Om appen är i testing kan refresh tokens löpa ut; använd lämplig publishing-konfiguration enligt Google. Detta går inte att utföra enbart från GitHub-anslutningen.

## Funktion
1. Välj ett sparat mejl i `public.kampanjmejl`.
2. Ange mottagarens e-postadress.
3. Välj **Skapa Gmail-utkast med bilder**.
4. Servern läser varje `bilaga_1`–`bilaga_3` via Neon S3.
5. En `<img src="cid:...">`-markör i `meddelande` matchas mot bildfilen i samma ordning.
6. En MIME-multipartsstruktur gör bilderna synliga i HTML och bifogar samma filer för nedladdning.
7. Gmail API `users.drafts.create` sparar ett utkast – ingen `send`-operation används.

Kampanjmejl 1 har redan bildmarkören `cid:minthis-collage` och `bilaga_1` satt till `Minthis-collage.jpg`.

## Verifiering
Utan korrekt konfigurerade hemligheter är exportknappen avstängd. Testa först med en intern testadress. Kontrollera i Gmail att collaget visas, att filen finns som bilaga och att mejlet är ett utkast. Sänd inte till festival innan bildrättigheterna är klarlagda.
