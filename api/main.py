"""API sécurisée de FactureFlow.

Les clés Supabase et Anthropic restent côté serveur. Chaque endpoint métier
exige un JWT Supabase et filtre systématiquement les données par user_id.
"""

import csv
import hashlib
import hmac
import io
import os
import tempfile

from fastapi import FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from supabase import create_client

from extract import extract_fields_image, extract_text, extract_with_retry, validate


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement requise : {name}")
    return value


supabase = create_client(
    required_env("SUPABASE_URL"),
    required_env("SUPABASE_SERVICE_ROLE_KEY"),
)

app = FastAPI(
    title="FactureFlow API",
    description="Extraction et validation de données de factures, par compte.",
    version="0.2.0",
)

default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Inbound-Secret"],
)

EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))


@app.get("/health")
def health():
    return {"status": "ok"}


def current_user_id(authorization: str | None = Header(default=None)) -> str:
    """Valide un JWT Supabase et retourne l'identifiant du client connecté."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentification requise")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user = supabase.auth.get_user(token).user
    except Exception as error:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée") from error
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    return user.id


def ensure_file_is_supported(file: UploadFile, content: bytes) -> str:
    filename = (file.filename or "").lower()
    if not filename.endswith(EXTENSIONS_PDF + EXTENSIONS_IMAGE):
        raise HTTPException(status_code=415, detail="Formats acceptés : PDF, JPG, JPEG, PNG")
    if not content:
        raise HTTPException(status_code=422, detail="Fichier vide")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop lourd")
    return filename


def detecter_doublon_logique(fields: dict, user_id: str):
    req = supabase.table("invoices").select("id").eq("user_id", user_id)
    if fields.get("fournisseur") and fields.get("numero_facture"):
        req = req.eq("fournisseur", fields["fournisseur"]).eq("numero_facture", fields["numero_facture"])
    elif fields.get("fournisseur") and fields.get("date") and fields.get("total") is not None:
        req = req.eq("fournisseur", fields["fournisseur"]).eq("date", fields["date"]).eq("total", fields["total"])
    else:
        return None
    result = req.execute()
    return result.data[0]["id"] if result.data else None


async def process_invoice(file: UploadFile, user_id: str, portee: str):
    if portee not in ("personnel", "entreprise"):
        raise HTTPException(status_code=422, detail="portee : personnel ou entreprise")

    content = await file.read()
    filename = ensure_file_is_supported(file, content)
    file_hash = hashlib.sha256(content).hexdigest()
    exact_duplicate = (
        supabase.table("invoices").select("id").eq("user_id", user_id).eq("file_hash", file_hash).execute()
    )
    if exact_duplicate.data:
        return {"fichier": file.filename, "verdict": "doublon", "id_existant": exact_duplicate.data[0]["id"]}

    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(content)
        temporary_path = temporary_file.name
    try:
        if filename.endswith(EXTENSIONS_PDF):
            fields, warnings = extract_with_retry(extract_text(temporary_path))
        else:
            fields = extract_fields_image(temporary_path)
            warnings = validate(fields)
    finally:
        os.unlink(temporary_path)

    duplicate_id = detecter_doublon_logique(fields, user_id)
    status = "doublon_potentiel" if duplicate_id else ("a_valider" if warnings else "ok")
    record = {
        **fields,
        "user_id": user_id,
        "statut": status,
        "portee": portee,
        "avertissements": warnings,
        "file_hash": file_hash,
        "fichier": file.filename,
    }
    inserted = supabase.table("invoices").insert(record).execute()
    return {
        "id": inserted.data[0]["id"],
        "fichier": file.filename,
        "donnees": fields,
        "avertissements": warnings,
        "verdict": status,
        "doublon_potentiel_de": duplicate_id,
    }


@app.post("/extract")
async def extract(file: UploadFile, portee: str = Form("personnel"), authorization: str | None = Header(default=None)):
    """Import manuel d'une facture depuis le tableau de bord connecté."""
    return await process_invoice(file, current_user_id(authorization), portee)


@app.post("/invoices/import")
async def import_invoice(file: UploadFile, portee: str = Form("personnel"), authorization: str | None = Header(default=None)):
    """Alias versionné de /extract pour les futurs clients API."""
    return await process_invoice(file, current_user_id(authorization), portee)


@app.get("/invoices")
def list_invoices(authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    return supabase.table("invoices").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data


CHAMPS_MODIFIABLES = {"fournisseur", "numero_facture", "date", "sous_total", "tps", "tvq", "total", "frais", "categorie", "type_document", "date_echeance", "statut", "portee"}


@app.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: str, changes: dict, authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    payload = {key: value for key, value in changes.items() if key in CHAMPS_MODIFIABLES}
    if not payload:
        raise HTTPException(status_code=400, detail="Aucun champ modifiable fourni")
    result = supabase.table("invoices").update(payload).eq("id", invoice_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return result.data[0]


@app.post("/invoices/{invoice_id}/valider")
def validate_invoice(invoice_id: str, authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    result = supabase.table("invoices").update({"statut": "ok", "avertissements": []}).eq("id", invoice_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return {"ok": True, "id": invoice_id}


@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    result = supabase.table("invoices").delete().eq("id", invoice_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return {"ok": True}


@app.get("/export.csv")
def export_csv(authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    rows = supabase.table("invoices").select("*").eq("user_id", user_id).order("date", desc=False).execute().data
    columns = ["date", "fournisseur", "categorie", "portee", "type_document", "numero_facture", "sous_total", "tps", "tvq", "frais", "total", "devise", "statut", "date_echeance"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return PlainTextResponse(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=factureflow.csv"})


@app.get("/me/inbound-address")
def inbound_address(authorization: str | None = Header(default=None)):
    user_id = current_user_id(authorization)
    profile = supabase.table("profiles").select("ingest_token").eq("id", user_id).single().execute().data
    domain = required_env("INBOUND_EMAIL_DOMAIN")
    return {"address": f"factures+{profile['ingest_token']}@{domain}"}


@app.post("/ingest/email")
async def ingest_email(file: UploadFile, recipient_token: str = Form(...), portee: str = Form("entreprise"), x_inbound_secret: str | None = Header(default=None)):
    """Endpoint réservé à n8n / à l'automatisation de réception email."""
    expected_secret = required_env("INBOUND_EMAIL_SECRET")
    if not x_inbound_secret or not hmac.compare_digest(x_inbound_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Canal email non autorisé")
    profile = supabase.table("profiles").select("id").eq("ingest_token", recipient_token).single().execute().data
    if not profile:
        raise HTTPException(status_code=404, detail="Adresse de dépôt inconnue")
    return await process_invoice(file, profile["id"], portee)
