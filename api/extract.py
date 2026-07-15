"""
FactureFlow — étape 1 : extraire le texte brut d'une facture PDF.

Usage :
    python extract.py ../samples/ma_facture.pdf
"""

import sys


def extract_text(pdf_path: str) -> str:
    """Retourne tout le texte du PDF.

    TODO (toi) :
      1. importe pdfplumber en haut du fichier
      2. ouvre le PDF avec pdfplumber.open(pdf_path)
      3. boucle sur les pages (pdf.pages)
      4. récupère le texte de chaque page avec page.extract_text()
      5. retourne le tout joint en une seule chaîne

    Indice : certaines pages peuvent retourner None — gère ce cas.
    """
    raise NotImplementedError("À toi de jouer — implémente extract_text()")


def extract_fields(text: str) -> dict:
    """Étape 2 (plus tard) : transformer le texte en données structurées
    (fournisseur, date, montants) avec l'API Claude.

    On s'en occupe quand extract_text() fonctionne.
    """
    raise NotImplementedError("Étape 2 — pas encore")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python extract.py <chemin_du_pdf>")
        sys.exit(1)

    text = extract_text(sys.argv[1])
    print("===== TEXTE EXTRAIT =====")
    print(text)
    print(f"\n({len(text)} caractères)")
