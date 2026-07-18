# Configuration N8N — ingestion de factures par courriel

Guide de référence pour recréer le workflow d'orchestration. N8N tourne en local
(`npx n8n` → http://localhost:5678) pendant que l'API FactureFlow tourne sur le port 8000.

## Vue d'ensemble

```
[Email Trigger (IMAP)] ──▶ [HTTP Request] ──▶ (l'API fait le reste :
 surveille la boîte          POST /extract      extraction, validation,
 courriel                    avec la pièce      anti-doublons, Supabase)
                             jointe
```

Un courriel avec une facture en pièce jointe et un mot-clé dans l'objet
(« facture », « receipt » ou « recu ») déclenche automatiquement tout le pipeline.

## Nœud 1 — Email Trigger (IMAP)

| Paramètre | Valeur |
|---|---|
| Credential | compte IMAP (voir plus bas) |
| Mailbox Name | `INBOX` |
| Action | `Mark as Read` — essentiel : évite le retraitement en boucle |
| Download Attachments | ✅ activé |
| Format | `Simple` |
| Property Prefix Name | `attachment_` (le suffixe numérique est ajouté par n8n) |

**Option « Custom Email Rules »** — ne réagir qu'aux courriels pertinents,
et ignorer le reste de la boîte :

```
[["UNSEEN"], ["OR", ["SUBJECT", "facture"], ["OR", ["SUBJECT", "receipt"], ["SUBJECT", "recu"]]]]
```

Syntaxe IMAP : `OR` ne prend que deux arguments, d'où l'emboîtement pour trois mots-clés.
La recherche ignore la casse; « recu » attrape aussi « reçu » sur la plupart des serveurs.

**Credential IMAP (Gmail)** :

| Champ | Valeur |
|---|---|
| User | l'adresse complète (`exemple@gmail.com`, pas juste `exemple`) |
| Password | un **mot de passe d'application** de 16 caractères (myaccount.google.com/apppasswords — exige la validation en deux étapes), jamais le mot de passe du compte |
| Host | `imap.gmail.com` |
| Port | `993` |
| SSL/TLS | ✅ |

Autres fournisseurs : `outlook.office365.com` (Outlook), `imap.mail.yahoo.com` (Yahoo),
`imap.mail.me.com` (iCloud) — même port, même workflow, seul le credential change.

## Nœud 2 — HTTP Request

| Paramètre | Valeur |
|---|---|
| Method | `POST` |
| URL | `http://127.0.0.1:8000/extract` ⚠️ voir piège IPv6 ci-dessous |
| Authentication | None |
| Send Body | ✅ |
| Body Content Type | `Form-Data` |

**Body Parameters :**

| Type | Name | Valeur |
|---|---|---|
| n8n Binary File | `file` | Input Data Field Name : `attachment_0` |
| Form Data | `portee` | `personnel` |

## Pièges rencontrés (et leurs solutions)

1. **`ECONNREFUSED ::1:8000`** — Node.js traduit « localhost » en IPv6 (`::1`),
   mais uvicorn n'écoute qu'en IPv4 (`127.0.0.1`). Solution : écrire `127.0.0.1`
   explicitement dans l'URL.
2. **Boîte pleine de non-lus** — sans Custom Email Rules, le déclencheur tente
   d'avaler tout l'historique non lu (1 200+ courriels). Les règles `SUBJECT`
   filtrent à la source.
3. **Le mot-clé doit être dans l'OBJET** du courriel, pas dans le corps.
4. **Action « Nothing » = boucle infinie** — avec un filtre `UNSEEN`, il faut
   `Mark as Read` après traitement, sinon les mêmes courriels sont repêchés
   à chaque cycle.
5. **Mode test vs mode actif** — « Execute step » sur le déclencheur pêche les
   courriels correspondants immédiatement; le mode **Active** (toggle) surveille
   en continu. L'écoute du mode test (« Execute workflow ») peut être capricieuse
   avec Gmail; le mode Active est le mode de référence.

## Comportement vérifié

- Facture PDF inédite par courriel → extraction complète → ligne dans Supabase
  → visible au dashboard après rafraîchissement.
- Même fichier envoyé deux fois → `verdict: doublon` avec `id_existant`,
  sans appel à l'IA (l'empreinte SHA-256 est vérifiée avant tout).

## Idée de second workflow (à venir)

Rappels d'échéances : Schedule Trigger quotidien → GET `/invoices` → nœud Code
qui filtre les factures dont `date_echeance` est dans ≤ 3 jours → courriel de rappel.
Deux types de déclencheurs (événement et horaire) sur la même API, sans nouvel endpoint.
