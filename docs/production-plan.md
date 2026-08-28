# Plan de mise en production FactureFlow

## 1. Créer le projet Supabase

1. Créer un projet Supabase distinct pour FactureFlow.
2. Exécuter `db/schema.sql`, puis `db/saas_migration.sql` dans le SQL Editor.
3. Activer l'authentification Email + mot de passe.
4. Configurer les URLs de redirection :
   - `http://127.0.0.1:5173`
   - `https://factureflow.evolutionb.ca`
5. Conserver `SUPABASE_SERVICE_ROLE_KEY` uniquement dans l'environnement de
   l'API. Le dashboard reçoit seulement la clé `anon`.

## 2. Déployer les deux services

| Service | URL | Rôle |
| --- | --- | --- |
| Dashboard React compilé | `factureflow.evolutionb.ca` | interface client |
| API FastAPI | `api.factureflow.evolutionb.ca` | IA, données et réception email |

Le dashboard peut aller sur cPanel après `npm run build`. L'API doit être
hébergée comme service Python permanent (Docker, Render, Railway, Fly.io ou
une application Python cPanel confirmée compatible).

## 3. Variables d'environnement de production

API : `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`,
`CORS_ORIGINS=https://factureflow.evolutionb.ca`, `INBOUND_EMAIL_DOMAIN`,
`INBOUND_EMAIL_SECRET`.

Dashboard : `VITE_API_URL=https://api.factureflow.evolutionb.ca`,
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

## 4. Réception email

Créer une boîte ou un routage entrant qui accepte `factures+*@factureflow.evolutionb.ca`.
N8N extrait le token de l'adresse de destination et transmet chaque pièce
jointe à l'API selon `email-ingestion.md`.

## 5. Avant l'ouverture publique

- vérifier l'inscription, connexion, déconnexion et mot de passe oublié;
- vérifier avec deux comptes que les factures sont isolées;
- vérifier l'import manuel et l'import email;
- activer SSL sur les deux sous-domaines;
- ajouter les liens FactureFlow sur evolutionb.ca.
