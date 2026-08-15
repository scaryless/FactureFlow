"""FactureFlow WSGI fallback for constrained cPanel hosting.

Uses only Python's standard library.  Secrets remain in cPanel environment
variables; this module is intentionally the only public Passenger entrypoint.
"""
import base64
import cgi
import csv
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 15 * 1024 * 1024
ORIGIN = os.getenv("CORS_ORIGINS", "https://factureflow.evolutionb.ca").split(",")[0].strip()

def response(start, status, payload=None, headers=None):
    raw = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    out = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(raw))),
           ("Access-Control-Allow-Origin", ORIGIN), ("Access-Control-Allow-Headers", "Authorization, Content-Type"),
           ("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")]
    if headers: out.extend(headers)
    start(status, out)
    return [raw]

def csv_response(start, rows):
    columns = ["date", "fournisseur", "categorie", "portee", "type_document", "numero_facture", "sous_total", "tps", "tvq", "frais", "total", "devise", "statut", "date_echeance"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    raw = output.getvalue().encode("utf-8")
    start("200 OK", [("Content-Type", "text/csv; charset=utf-8"), ("Content-Length", str(len(raw))),
                      ("Content-Disposition", "attachment; filename=factureflow.csv"), ("Access-Control-Allow-Origin", ORIGIN)])
    return [raw]

def json_body(environ):
    size = int(environ.get("CONTENT_LENGTH") or 0)
    return json.loads(environ["wsgi.input"].read(size) or b"{}")

def env(name):
    value = os.getenv(name)
    if not value: raise RuntimeError("Missing required server configuration")
    return value

def request_json(url, method="GET", data=None, headers=None):
    h = {"Accept": "application/json", **(headers or {})}
    body = None if data is None else json.dumps(data).encode()
    if body: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=45) as result:
        return json.loads(result.read() or b"{}")

def current_user(environ):
    auth = environ.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "): raise PermissionError("Authentification requise")
    token = auth[7:].strip()
    user = request_json(env("SUPABASE_URL") + "/auth/v1/user", headers={"apikey": env("SUPABASE_SERVICE_ROLE_KEY"), "Authorization": "Bearer " + token})
    if not user.get("id"): raise PermissionError("Session invalide")
    return user["id"]

def supabase(path, method="GET", data=None):
    key = env("SUPABASE_SERVICE_ROLE_KEY")
    return request_json(env("SUPABASE_URL") + "/rest/v1/" + path, method, data, {"apikey": key, "Authorization": "Bearer " + key, "Prefer": "return=representation"})

def extract_invoice(blob, filename):
    suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix not in ("pdf", "png", "jpg", "jpeg"): raise ValueError("Formats acceptés : PDF, JPG, JPEG, PNG")
    if not blob or len(blob) > MAX_BYTES: raise ValueError("Fichier vide ou trop lourd")
    kind = "application/pdf" if suffix == "pdf" else ("image/jpeg" if suffix in ("jpg", "jpeg") else "image/png")
    encoded = base64.b64encode(blob).decode()
    part = {"type": "input_file", "filename": filename, "file_data": "data:%s;base64,%s" % (kind, encoded)} if suffix == "pdf" else {"type": "input_image", "image_url": "data:%s;base64,%s" % (kind, encoded)}
    prompt = "Extract this invoice. Return ONLY valid JSON with fournisseur, numero_facture, date (YYYY-MM-DD if known), sous_total, tps, tvq, total, devise, categorie, type_document, date_echeance. Use null when unknown."
    result = request_json("https://api.openai.com/v1/responses", "POST", {"model":"gpt-4.1-mini", "input":[{"role":"user", "content":[{"type":"input_text", "text":prompt}, part]}]}, {"Authorization":"Bearer " + env("OPENAI_API_KEY")})
    text = result.get("output_text", "")
    match = re.search(r"\{.*\}", text, re.S)
    if not match: raise ValueError("Extraction IA invalide")
    return json.loads(match.group(0))

def application(environ, start_response):
    try:
        path, method = environ.get("PATH_INFO", "/"), environ.get("REQUEST_METHOD", "GET")
        if method == "OPTIONS": return response(start_response, "204 No Content")
        if path == "/health": return response(start_response, "200 OK", {"status":"ok", "runtime":"wsgi"})
        user_id = current_user(environ)
        if path == "/invoices" and method == "GET":
            return response(start_response, "200 OK", supabase("invoices?user_id=eq.%s&order=created_at.desc" % urllib.parse.quote(user_id)))
        if path == "/export.csv" and method == "GET":
            rows = supabase("invoices?user_id=eq.%s&order=date.asc" % urllib.parse.quote(user_id))
            return csv_response(start_response, rows)
        if path in ("/extract", "/invoices/import") and method == "POST":
            form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
            upload = form["file"] if "file" in form else None
            if not upload or not getattr(upload, "file", None): raise ValueError("Fichier manquant")
            blob, filename = upload.file.read(), (upload.filename or "facture")
            fields = extract_invoice(blob, filename)
            record = {**fields, "user_id":user_id, "fichier":filename, "file_hash":hashlib.sha256(blob).hexdigest(), "portee":form.getfirst("portee", "personnel"), "statut":"a_valider", "avertissements":[]}
            inserted = supabase("invoices", "POST", record)
            return response(start_response, "200 OK", {"id":inserted[0]["id"], "fichier":filename, "donnees":fields, "verdict":"a_valider"})
        match = re.fullmatch(r"/invoices/([0-9a-f-]{36})(?:/(valider))?", path)
        if match:
            invoice_id, action = match.groups()
            target = "invoices?id=eq.%s&user_id=eq.%s" % (urllib.parse.quote(invoice_id), urllib.parse.quote(user_id))
            if action == "valider" and method == "POST":
                result = supabase(target, "PATCH", {"statut":"ok", "avertissements":[]})
                return response(start_response, "200 OK", {"ok":bool(result), "id":invoice_id})
            if not action and method == "PATCH":
                allowed = {"fournisseur", "numero_facture", "date", "sous_total", "tps", "tvq", "total", "frais", "categorie", "type_document", "date_echeance", "statut", "portee"}
                changes = {k:v for k,v in json_body(environ).items() if k in allowed}
                if not changes: raise ValueError("Aucun champ modifiable fourni")
                result = supabase(target, "PATCH", changes)
                return response(start_response, "200 OK", result[0] if result else {"detail":"Facture introuvable"})
            if not action and method == "DELETE":
                result = supabase(target, "DELETE")
                return response(start_response, "200 OK", {"ok":bool(result), "id":invoice_id})
        return response(start_response, "404 Not Found", {"detail":"Route introuvable"})
    except PermissionError as error:
        return response(start_response, "401 Unauthorized", {"detail":str(error)})
    except (ValueError, urllib.error.HTTPError) as error:
        return response(start_response, "422 Unprocessable Entity", {"detail":str(error)})
    except Exception:
        return response(start_response, "500 Internal Server Error", {"detail":"Erreur serveur"})
