"""
FactureFlow — étape 1 : extraire le texte brut d'une facture PDF.

Usage :
    python extract.py ../samples/ma_facture.pdf
"""

import sys

import pdfplumber


def extract_text(pdf_path: str) -> str:
    """Retourne tout le texte du PDF."""
    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    return "\n".join(pages_text)


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
