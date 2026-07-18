"""
FactureFlow — API web.

Lancement (depuis api/, venv actif) :
    uvicorn main:app --reload

Documentation interactive : http://127.0.0.1:8000/docs
"""

import csv
import hashlib
import io
import os
import tempfile

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from supabase import create_client

from extract import (extract_fields_image, extract_text,
                     extract_with_retry, validate)

# extract.py a déjà chargé le .env — les variables sont disponibles.
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

app = FastAPI(
    title="FactureFlow API",
    description="Extraction et validation de données de factures (PDF et photos).",
    version="0.1.0",
)

# Autorise le dashboard local à appeler l'API depuis le navigateur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png")


@app.get("/health")
def health():
    """Vérification simple que le service est en vie."""
    return {"status": "ok"}


def detecter_doublon_logique(fields: dict):
    """Anti-doublons couche 2 : même facture déjà en base sous un autre
    fichier (ex. la même facture en PDF et en photo). Retourne l'id
    de la facture existante, ou None."""
    req = supabase.table("invoices").select("id")

    if fields.get("fournisseur") and fields.get("numero_facture"):
        req = (req.eq("fournisseur", fields["fournisseur"])
                  .eq("numero_facture", fields["numero_facture"]))
    elif (fields.get("fournisseur") and fields.get("date")
          and fields.get("total") is not None):
        req = (req.eq("fournisseur", fields["fournisseur"])
                  .eq("date", fields["date"])
                  .eq("total", fields["total"]))
    else:
        return None  # pas assez d'informations pour comparer

    resultat = req.execute()
    return resultat.data[0]["id"] if resultat.data else None


@app.post("/extract")
async def extract(file: UploadFile, portee: str = Form("personnel")):
    """Reçoit une facture (PDF ou photo) et sa portée (personnel ou
    entreprise), l'extrait, la valide, la stocke, et retourne le tout."""
    if portee not in ("personnel", "entreprise"):
        raise HTTPException(status_code=422, detail="portee : personnel ou entreprise")

    nom = (file.filename or "").lower()

    if not nom.endswith(EXTENSIONS_PDF + EXTENSIONS_IMAGE):
        raise HTTPException(
            status_code=415,
            detail="Format non pris en charge. Acceptés : .pdf, .jpg, .jpeg, .png",
        )

    contenu = await file.read()

    # Anti-doublons couche 1 : empreinte du fichier. Si le même fichier
    # exact a déjà été traité, on ne refait ni l'extraction ni l'insertion.
    file_hash = hashlib.sha256(contenu).hexdigest()
    deja_vu = (supabase.table("invoices").select("id")
               .eq("file_hash", file_hash).execute())
    if deja_vu.data:
        return {
            "fichier": file.filename,
            "verdict": "doublon",
            "message": "Ce fichier exact a déjà été traité.",
            "id_existant": deja_vu.data[0]["id"],
        }

    # On écrit le fichier reçu dans un fichier temporaire, car nos
    # fonctions d'extraction travaillent avec des chemins de fichiers.
    suffixe = os.path.splitext(nom)[1]
    with tempfile.NamedTemporaryFile(suffix=suffixe, delete=False) as tmp:
        tmp.write(contenu)
        chemin = tmp.name

    try:
        if nom.endswith(EXTENSIONS_PDF):
            texte = extract_text(chemin)
            fields, avertissements = extract_with_retry(texte)
        else:
            fields = extract_fields_image(chemin)
            avertissements = validate(fields)
    finally:
        os.unlink(chemin)  # on ne garde jamais le fichier sur le serveur

    # Statut : validation d'abord, doublon logique ensuite.
    statut = "a_valider" if avertissements else "ok"
    doublon_id = detecter_doublon_logique(fields)
    if doublon_id:
        statut = "doublon_potentiel"

    enregistrement = {
        **fields,
        "statut": statut,
        "portee": portee,
        "avertissements": avertissements,
        "file_hash": file_hash,
        "fichier": file.filename,
    }
    insertion = supabase.table("invoices").insert(enregistrement).execute()

    return {
        "id": insertion.data[0]["id"],
        "fichier": file.filename,
        "donnees": fields,
        "avertissements": avertissements,
        "verdict": statut,
        "doublon_potentiel_de": doublon_id,
    }


@app.get("/invoices")
def list_invoices():
    """Toutes les factures, les plus récentes d'abord — pour le dashboard."""
    resultat = (supabase.table("invoices").select("*")
                .order("created_at", desc=True).execute())
    return resultat.data


CHAMPS_MODIFIABLES = {
    "fournisseur", "numero_facture", "date", "sous_total", "tps", "tvq",
    "total", "frais", "categorie", "type_document", "date_echeance", "statut",
    "portee",
}


@app.patch("/invoices/{invoice_id}")
def modifier_invoice(invoice_id: str, changements: dict):
    """Correction humaine : modifie un ou plusieurs champs d'une facture.
    Seuls les champs de la liste blanche sont acceptés."""
    donnees = {k: v for k, v in changements.items() if k in CHAMPS_MODIFIABLES}
    if not donnees:
        raise HTTPException(status_code=400, detail="Aucun champ modifiable fourni")
    resultat = (supabase.table("invoices").update(donnees)
                .eq("id", invoice_id).execute())
    if not resultat.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return resultat.data[0]


@app.post("/invoices/{invoice_id}/valider")
def valider_invoice(invoice_id: str):
    """Validation humaine : l'utilisateur confirme une facture douteuse."""
    resultat = (supabase.table("invoices")
                .update({"statut": "ok", "avertissements": []})
                .eq("id", invoice_id).execute())
    if not resultat.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return {"ok": True, "id": invoice_id}


@app.delete("/invoices/{invoice_id}")
def supprimer_invoice(invoice_id: str):
    """Supprime une facture (ex. un doublon confirmé par l'utilisateur)."""
    resultat = (supabase.table("invoices").delete()
                .eq("id", invoice_id).execute())
    if not resultat.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return {"ok": True}


@app.get("/export.csv")
def export_csv():
    """Export comptable : toutes les factures en CSV."""
    lignes = (supabase.table("invoices").select("*")
              .order("date", desc=False).execute()).data

    colonnes = ["date", "fournisseur", "categorie", "portee", "type_document",
                "numero_facture", "sous_total", "tps", "tvq", "frais", "total",
                "devise", "statut", "date_echeance"]

    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=colonnes, extrasaction="ignore")
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(ligne)

    return PlainTextResponse(
        tampon.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=factureflow.csv"},
    )
