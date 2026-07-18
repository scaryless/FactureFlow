-- FactureFlow — schéma de la base de données (Supabase / PostgreSQL)
-- Pour recréer la base : coller ce fichier dans le SQL Editor de Supabase.

create table invoices (
  id uuid primary key default gen_random_uuid(),
  fournisseur text,
  numero_facture text,
  date date,
  sous_total numeric(10,2),
  tps numeric(10,2),
  tvq numeric(10,2),
  frais numeric(10,2),                 -- frais d'administration, de retard, etc.
  total numeric(10,2),
  dernier_paiement numeric(10,2),
  date_dernier_paiement date,
  type_document text,
  categorie text,
  date_echeance date,
  devise text default 'CAD',
  statut text default 'ok',            -- ok | a_valider | doublon_potentiel
  portee text default 'personnel',     -- personnel | entreprise
  avertissements text[],               -- liste produite par validate()
  file_hash text unique,               -- anti-doublons couche 1 (SHA-256 du fichier)
  fichier text,                        -- nom du fichier d'origine
  created_at timestamptz default now()
);

-- Sécurité : table verrouillée pour les clés client (anon/authenticated).
-- Seul le serveur (clé service_role) y accède — tout passe par l'API.
alter table invoices enable row level security;
