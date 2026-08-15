-- FactureFlow SaaS — migration multi-utilisateurs Supabase
-- À exécuter dans le SQL Editor Supabase, après db/schema.sql.

create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  ingest_token text not null unique default replace(gen_random_uuid()::text, '-', ''),
  created_at timestamptz not null default now()
);

-- Crée automatiquement le profil et son code d'import quand un client
-- s'inscrit dans Supabase Auth.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

alter table public.invoices add column if not exists user_id uuid references auth.users(id) on delete cascade;

-- Une facture identique peut exister dans deux comptes différents.
alter table public.invoices drop constraint if exists invoices_file_hash_key;
create unique index if not exists invoices_user_file_hash_unique
  on public.invoices (user_id, file_hash);
create index if not exists invoices_user_created_at_index
  on public.invoices (user_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.invoices enable row level security;

drop policy if exists "profiles: owner can read" on public.profiles;
create policy "profiles: owner can read" on public.profiles
  for select to authenticated using (id = auth.uid());

drop policy if exists "invoices: owner can read" on public.invoices;
create policy "invoices: owner can read" on public.invoices
  for select to authenticated using (user_id = auth.uid());

drop policy if exists "invoices: owner can insert" on public.invoices;
create policy "invoices: owner can insert" on public.invoices
  for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "invoices: owner can update" on public.invoices;
create policy "invoices: owner can update" on public.invoices
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "invoices: owner can delete" on public.invoices;
create policy "invoices: owner can delete" on public.invoices
  for delete to authenticated using (user_id = auth.uid());

-- Vérification avant lancement : aucune ancienne facture ne doit rester
-- sans propriétaire. Attribue-les explicitement à un compte administrateur
-- avant de rendre user_id obligatoire.
-- select id, fichier from public.invoices where user_id is null;
