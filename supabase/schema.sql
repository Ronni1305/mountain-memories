-- Mountain Memories – Datenbankstruktur für Supabase
-- Einmalig im Supabase-Dashboard unter „SQL Editor“ → „New query“ einfügen und „Run“ drücken.
-- Das Skript kann gefahrlos mehrmals ausgeführt werden.

-- ------------------------------------------------------------------------------------------
-- Tabellen
-- ------------------------------------------------------------------------------------------
create table if not exists public.tours (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
    art           text not null check (art in ('wandern', 'klettern', 'bergsteigen')),
    name          text not null check (length(trim(name)) > 0),
    datum         date not null,
    lat           double precision not null check (lat between -90 and 90),
    lon           double precision not null check (lon between -180 and 180),
    hoehe_m       integer check (hoehe_m between -450 and 8900),
    hoehe_quelle  text check (hoehe_quelle in ('osm', 'dem', 'manuell')),
    region        text,
    dauer_min     integer check (dauer_min > 0),
    partner       text,
    ausgangspunkt text,
    ziel          text,
    hm_auf        integer check (hm_auf between 0 and 10000),
    hm_ab         integer check (hm_ab between 0 and 10000),
    schwierigkeit text,
    wetter        text,
    bericht       text,
    bewertung     smallint check (bewertung between 1 and 5),
    favorit       boolean not null default false,
    titelbild_id  uuid,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists public.photos (
    id           uuid primary key default gen_random_uuid(),
    tour_id      uuid not null references public.tours(id) on delete cascade,
    user_id      uuid not null default auth.uid() references auth.users(id) on delete cascade,
    pfad         text not null unique,
    thumb_pfad   text not null unique,
    dateiname    text,
    beschriftung text,
    breite       integer,
    hoehe        integer,
    bytes        integer,
    created_at   timestamptz not null default now()
);

create index if not exists tours_user_datum on public.tours (user_id, datum desc);
create index if not exists photos_tour on public.photos (tour_id);

-- Spalten, die nach der ersten Version dazugekommen sind
alter table public.tours add column if not exists favorit boolean not null default false;

-- Titelbild: zeigt auf ein Foto; wird das Foto gelöscht, wird das Feld automatisch leer.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'tours_titelbild_fk') then
        alter table public.tours
            add constraint tours_titelbild_fk foreign key (titelbild_id)
            references public.photos(id) on delete set null;
    end if;
end $$;

-- updated_at bei jeder Änderung setzen
create or replace function public.mm_set_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

drop trigger if exists tours_updated_at on public.tours;
create trigger tours_updated_at before update on public.tours
    for each row execute function public.mm_set_updated_at();

-- ------------------------------------------------------------------------------------------
-- Row Level Security: jede Person sieht und ändert nur ihre eigenen Zeilen
-- ------------------------------------------------------------------------------------------
alter table public.tours  enable row level security;
alter table public.photos enable row level security;

drop policy if exists "tours_eigene" on public.tours;
create policy "tours_eigene" on public.tours
    for all to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));

drop policy if exists "photos_eigene" on public.photos;
create policy "photos_eigene" on public.photos
    for all to authenticated
    using (user_id = (select auth.uid()))
    with check (
        user_id = (select auth.uid())
        and exists (select 1 from public.tours t where t.id = tour_id and t.user_id = (select auth.uid()))
    );

-- Nicht angemeldete Besucher (Rolle „anon“) bekommen überhaupt keine Rechte.
revoke all on public.tours, public.photos from anon;
grant select, insert, update, delete on public.tours, public.photos to authenticated;

-- ------------------------------------------------------------------------------------------
-- Foto-Ablage: privater Bucket, Zugriff nur auf den eigenen Ordner <user_id>/...
-- ------------------------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', false, 10485760, array['image/jpeg'])
on conflict (id) do update
    set public = false,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "fotos_lesen" on storage.objects;
create policy "fotos_lesen" on storage.objects
    for select to authenticated
    using (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "fotos_hochladen" on storage.objects;
create policy "fotos_hochladen" on storage.objects
    for insert to authenticated
    with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "fotos_loeschen" on storage.objects;
create policy "fotos_loeschen" on storage.objects
    for delete to authenticated
    using (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);
