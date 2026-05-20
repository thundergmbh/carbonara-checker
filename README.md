# Dolce Pensiero Carbonara Checker

Wöchentlicher Cronjob auf GitHub Actions, der prüft ob im Wochenmenü von
[Dolce Pensiero](https://dolcepensiero.at/menu/menu-der-woche) ein
Carbonara-Gericht erscheint — bevorzugt am Mittwoch — und das Ergebnis in
einen Slack-Channel postet.

## Repo-Struktur

```
.
├── .github/
│   └── workflows/
│       └── carbonara.yml      # Workflow (siehe carbonara.yml in diesem Bundle)
├── carbonara_check.py
├── requirements.txt
└── README.md
```

Das `carbonara.yml` aus diesem Bundle gehört nach `.github/workflows/`.

## Setup (einmalig)

1. **Slack Incoming Webhook anlegen**
   - <https://api.slack.com/apps> → *Create New App* → *From scratch*
   - App benennen (z.B. „Carbonara Bot"), Workspace wählen
   - *Incoming Webhooks* → aktivieren → *Add New Webhook to Workspace*
   - Channel wählen → kopierte URL (Format `https://hooks.slack.com/services/T…/B…/…`) merken

2. **Repo anlegen + Files committen**
   ```bash
   git init carbonara-checker && cd carbonara-checker
   # die vier Files aus diesem Bundle reinkopieren (yml nach .github/workflows/)
   git add . && git commit -m "init"
   gh repo create carbonara-checker --private --source=. --push
   ```

3. **Secret hinterlegen**
   - Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*
   - Name: `SLACK_WEBHOOK_URL`
   - Value: die Webhook-URL aus Schritt 1

4. **Manuell testen**
   - Repo → *Actions* → *Carbonara Check* → *Run workflow*
   - Logs ansehen — die Slack-Nachricht sollte erscheinen.

## Nachrichten-Varianten

| Fall                           | Slack-Output                                                                |
|--------------------------------|------------------------------------------------------------------------------|
| Carbonara am Mittwoch          | 🍝 *Carbonara am Mittwoch!* Diese Woche im Programm bei Dolce Pensiero.      |
| Carbonara an anderem Tag       | 🍝 Keine Carbonara am Mittwoch — aber am *Dienstag, Freitag*.                |
| Diese Woche keine Carbonara    | ❌ Diese Woche steht *keine Carbonara* auf dem Menü von Dolce Pensiero.       |
| Menü noch nicht veröffentlicht | ⏳ Das Wochenmenü ist noch nicht veröffentlicht.                              |

## Cron anpassen

Default: Montag 09:00 Wien (CEST). Wenn du z.B. Mittwoch früh willst:

```yaml
- cron: '0 5 * * 3'   # Mittwoch 07:00 Wien (CEST)
```

## Lokal testen

```bash
pip install -r requirements.txt
playwright install chromium
export SLACK_WEBHOOK_URL="https://hooks.slack.com/…"   # optional
python carbonara_check.py
```

Ohne `SLACK_WEBHOOK_URL` wird der Payload nur in stdout ausgegeben — nützlich
zum Debuggen ohne den Channel zu fluten.

## Falls die Seitenstruktur sich ändert

Der Parser sucht die deutschen Wochentage als Textmarker und sammelt den
Text bis zum nächsten Wochentag als „Tagesabschnitt". Falls Dolce Pensiero
das Layout ändert und dadurch z.B. das Wort „Mittwoch" mehrfach auftaucht
oder fehlt, im Log nachsehen welche Sections gefunden wurden — der Print
`Carbonara-Tage: […]` zeigt das direkt.
