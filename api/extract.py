"""
FactureFlow — extraction et validation de données de factures.

Usage :
    python extract.py ../samples/ma_facture.pdf
"""

import json
import sys
import re  # pour trouver les dates dans le texte
from datetime import datetime

import anthropic
import pdfplumber
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()


def extract_text(pdf_path: str) -> str:
    """Retourne tout le texte du PDF."""
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
5. Attention aux dates ambiguës (ex. « 26 06 24 ») : cherche l'en-tête de \
format à proximité (« A.-Y. MO. J.-D. » signifie année-mois-jour). Vérifie \
ensuite la cohérence : toutes les dates d'un même document sont proches \
dans le temps. Une date d'émission se situe quelques semaines avant la \
date d'échéance, jamais deux ans avant. Corrige ton interprétation si les \
dates sont incohérentes entre elles.
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


def _json_de_reponse(response) -> dict:
    """Extrait le JSON du bloc texte d'une réponse API.

    Certains modèles (ex. Sonnet) renvoient d'abord un bloc de réflexion
    (ThinkingBlock) avant le texte : on cherche le bloc de type "text"
    au lieu de supposer que c'est le premier.
    """
    raw = None
    for bloc in response.content:
        if bloc.type == "text":
            raw = bloc.text.strip()
            break
    if raw is None:
        raise ValueError("Réponse API sans bloc texte")

    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    return json.loads(raw)


def extract_fields(text: str) -> dict:
    """Transforme le texte d'une facture en données structurées via Claude."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": TON_PROMPT + "\n\n" + text}],
    )
    return _json_de_reponse(response)


def validate(fields: dict) -> list:
    """Vérifie la cohérence des données extraites. Retourne les avertissements.

    Validation 100 % locale : aucun appel API, donc aucun coût.
    """
    warnings = []

    montants = [fields.get("sous_total"), fields.get("tps"),
                fields.get("tvq"), fields.get("total")]
    if all(m is not None for m in montants):
        somme = fields["sous_total"] + fields["tps"] + fields["tvq"]
        if abs(somme - fields["total"]) >= 0.02:
            warnings.append(f"montants incohérents : {somme:.2f} ≠ {fields['total']:.2f}")

    if fields.get("date") and fields.get("date_echeance"):
        emission = datetime.strptime(fields["date"], "%Y-%m-%d")
        echeance = datetime.strptime(fields["date_echeance"], "%Y-%m-%d")
        ecart = (echeance - emission).days
        if ecart < 0 or ecart > 90:
            warnings.append(f"dates incohérentes : {ecart} jours entre émission et échéance")

    if fields.get("total") is None:
        warnings.append("total manquant")

    return warnings


def corriger_dates_par_ancres(fields: dict, text: str) -> dict:
    """Réparation en code pur, sans IA : si une date extraite correspond à
    une date écrite en toutes lettres dans le document (même mois, même jour)
    mais avec une année différente, on prend l'année du document — l'ancre.
    L'IA ne peut pas contredire ce que le regex a prouvé."""
    ancres = [d.replace("/", "-")
              for d in re.findall(r"\b20\d{2}[/-]\d{2}[/-]\d{2}\b", text)]

    for champ in ("date", "date_echeance", "date_dernier_paiement"):
        valeur = fields.get(champ)
        if not valeur:
            continue
        for ancre in ancres:
            # valeur[5:] = "MM-JJ" : même mois et jour, mais année différente
            if valeur[5:] == ancre[5:] and valeur != ancre:
                print(f"(correction code : {champ} {valeur} -> {ancre})")
                fields[champ] = ancre

    return fields


def extract_with_retry(text: str) -> tuple[dict, list]:
    """Extrait et valide; en cas d'incohérence, redonne au modèle sa propre
    sortie avec les erreurs détectées et lui demande de corriger (une seule
    reprise, uniquement pour les documents à problème)."""
    fields = extract_fields(text)
    fields = corriger_dates_par_ancres(fields, text)
    warnings = validate(fields)

    if warnings:
        print(f"(autocorrection : {'; '.join(warnings)})")
        dates_sures = re.findall(r"\b20\d{2}[/-]\d{2}[/-]\d{2}\b", text)
        correction = (
            TON_PROMPT + "\n\n" + text
            + "\n\nUne première extraction a donné : " + json.dumps(fields, ensure_ascii=False)
            + "\nMais la validation a détecté ces problèmes : " + "; ".join(warnings)
            + "\nDates au format explicite trouvées dans le document (fiables, "
            + "ne les contredis pas) : " + ", ".join(dates_sures)
            + "\nCorrige ces incohérences et retourne le JSON complet corrigé, "
            + "en respectant toutes les règles."
        )
        response = client.messages.create(
            model="claude-sonnet-5",  # escalade : modèle plus fort pour les cas difficiles
            max_tokens=1024,
            messages=[{"role": "user", "content": correction}],
        )
        fields_corriges = _json_de_reponse(response)
        fields_corriges = corriger_dates_par_ancres(fields_corriges, text)

        warnings_corriges = validate(fields_corriges)
        if not warnings_corriges:
            return fields_corriges, []  # la correction a réglé le problème

        # La reprise n'a pas suffi : on garde la première version,
        # avec ses avertissements — l'humain tranchera.

    return fields, warnings


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
    fields, avertissements = extract_with_retry(text)
    print(json.dumps(fields, indent=2, ensure_ascii=False))
    print("--------------------------------")
    print(f"({len(fields)} champs)")

    print("\n===== VALIDATION =====")
    if avertissements:
        print("VERDICT : À VALIDER")
        for a in avertissements:
            print(f"  - {a}")
    else:
        print("VERDICT : OK")
