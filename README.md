# FactureFlow — Extracteur de factures automatisé

> Prenez vos factures en photo ou téléversez un PDF, et leurs données (fournisseur, date, montants, taxes) sont extraites par l'IA, puis stockées automatiquement dans une base de données. Le tout se consulte dans un tableau de bord simple, avec export CSV pour la comptabilité ou les impôts.

## Le problème

Le moment des impôts arrive et vous ne savez plus où sont vos factures — vous n'en retrouvez que quelques-unes. Reçus de gaz froissés dans l'auto, factures d'Hydro perdues dans les courriels, relevés de cellulaire jamais téléchargés : retranscrire tout ça à la main prend des heures, et on en oublie toujours.

Ce problème touche autant les particuliers que les petites entreprises, où la saisie manuelle des factures fournisseurs gruge un temps précieux chaque mois.

## La solution

FactureFlow automatise la corvée du début à la fin :

1. Vous déposez une facture — PDF (Hydro, cellulaire, achat en ligne) ou simple photo prise avec votre téléphone (reçu de gaz, de restaurant).
2. L'intelligence artificielle lit le document et en extrait les données clés : fournisseur, numéro de facture, date, sous-total, TPS, TVQ, total.
3. Le système vérifie la cohérence des montants et attribue un score de confiance. En cas de doute, la facture est marquée « à valider » — un humain garde toujours le dernier mot.
4. Tout s'affiche dans un tableau de bord : dépenses par mois, filtres par fournisseur, export CSV en un clic.

*(Capture d'écran du tableau de bord à venir.)*

## Comment ça fonctionne

```
[Dépôt]                     [Extraction]                [Stockage]        [Consultation]
Photo ou PDF   ──────▶   API Python (FastAPI)   ──▶   Supabase    ──▶   Dashboard React
                          1. Lecture du PDF            (PostgreSQL)      - liste et filtres
                          (pdfplumber) ou de           factures +        - totaux par mois
                          l'image directement          fournisseurs      - validation humaine
                          2. Claude AI extrait                           - export CSV
                          un JSON structuré
                          3. Validation des
                          montants + score
                          de confiance
```

En mots simples : quand une facture arrive, un programme la lit (qu'elle soit un PDF ou une photo), demande à une IA d'en tirer les informations importantes, vérifie que les chiffres se tiennent (sous-total + taxes = total), puis range le tout dans une base de données. Le tableau de bord ne fait qu'afficher ce qui s'y trouve — comme un classeur, mais qui se remplit tout seul.

## Lancer en local

```bash
cd api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python extract.py ../samples/ma_facture.pdf
```

## Feuille de route

- [x] Extraction du texte des PDF (pdfplumber)
- [ ] Extraction structurée avec l'API Claude (PDF et photos)
- [ ] Validation des montants et score de confiance
- [ ] API REST (FastAPI) + base de données Supabase
- [ ] Tableau de bord React avec export CSV
- [ ] Application mobile de capture (React Native / Expo)

## Limites connues

- Les factures manuscrites ne sont pas prises en charge.
- Une seule devise (CAD) pour l'instant.
- Les photos floues ou mal cadrées réduisent la qualité de l'extraction — le score de confiance le signale.

---

*English summary: FactureFlow extracts structured data (vendor, date, amounts, taxes) from invoice PDFs and receipt photos using AI, validates the amounts, stores everything in PostgreSQL, and displays it in a React dashboard with CSV export.*
