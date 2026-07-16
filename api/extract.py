
import sys

import json

import pdfplumber
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()


def extract_text(pdf_path: str) -> str:

    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    return "\n".join(pages_text)

TON_PROMPT = """Tu es un extracteur de données de factures. On te fournit le texte brut \
d'une facture ou d'un reçu (souvent en français du Québec, parfois en anglais).

Retourne UNIQUEMENT un objet JSON valide, sans aucun texte avant ou après, \
sans balises Markdown, avec exactement ces champs :

- "fournisseur" : le nom de l'entreprise qui a émis la facture (chaîne)
- "numero_facture" : le numéro de facture ou de reçu (chaîne)
- "date" : la date d'émission au format AAAA-MM-JJ (chaîne)
- "sous_total" : le montant avant taxes (nombre)
- "tps" : le montant de la TPS (nombre)
- "tvq" : le montant de la TVQ (nombre)
- "total" : le montant total payé (nombre)
- "dernier_paiement" : le montant du dernier paiement reçu (nombre)
- "date_dernier_paiement" : la date de ce paiement au format AAAA-MM-JJ (chaîne)
- "type_document" : "facture", "recu" ou "releve_carte" (chaîne)
- "categorie" : une valeur parmi "energie", "telecom", "essence", "epicerie", \
"restaurant", "credit", "autre" (chaîne)
- "date_echeance" : la date limite de paiement au format AAAA-MM-JJ (chaîne)
- "devise" : le code de la devise, par défaut "CAD" (chaîne)

Règles :
1. Si une information est introuvable dans le texte, mets null — n'invente jamais.
2. Les montants sont des nombres avec un point décimal (12,34 $ devient 12.34), \
jamais des chaînes, sans symbole de devise.
3. S'il y a plusieurs dates, "date" est la date d'émission, \
"date_echeance" est la date limite de paiement.
4. Ne confonds pas TPS (5 %) et TVQ (9,975 %) : vérifie les taux si les \
étiquettes sont ambiguës.
5. Attention aux dates ambiguës : cherche l'en-tête de format à proximité \
(ex. « A.-Y. MO. J.-D. » signifie année-mois-jour). En cas de doute, \
privilégie l'interprétation où l'année est plausible (2020-2030).
6. Pour les relevés de carte de crédit : le dernier paiement est la ligne \
du type « PAIEMENT RECU » ou « PAYMENT RECEIVED ». Le montant est positif \
(75.00- sur le relevé signifie un paiement de 75.00). Pour une facture \
ordinaire sans historique de paiement, mets null.
7. "categorie" doit être exactement une des sept valeurs de la liste — \
jamais une autre. Si aucune ne convient clairement, mets "autre".

Exemple de sortie :
{"fournisseur": "Hydro-Québec", "numero_facture": "652 401 578", "date": "2026-05-14", "sous_total": 87.20, "tps": 4.36, "tvq": 8.70, "total": 100.26, "dernier_paiement": null, "date_dernier_paiement": null, "type_document": "facture", "categorie": "energie", "date_echeance": "2026-06-05", "devise": "CAD"}

Voici le texte de la facture :
"""

def extract_fields(text: str) -> dict:
    """Transforme le texte d'une facture en données structurées via Claude."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": TON_PROMPT + "\n\n" + text}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw =  raw.strip("`").removeprefix("json").strip()

    return json.loads(raw)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python extract.py <chemin_du_pdf>")
        sys.exit(1)

    text = extract_text(sys.argv[1])
    print("===== TEXTE EXTRAIT =====")
    print(text)
    print(f"\n({len(text)} caractères)")
    print("--------------------------------")
    print("\n===== DONNÉES STRUCTURÉES =====")
    fields = extract_fields(text)
    print(json.dumps(fields, indent=2, ensure_ascii=False))
    print("--------------------------------")
    print(f"\n({len(fields)} champs)")
    print("--------------------------------")