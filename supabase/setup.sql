-- ============================================================
-- EILAT MOTORS · Banco do site (Supabase)
-- Cole tudo no SQL Editor do Supabase e clique em Run.
-- Antes de rodar, troque o e-mail na seção 7 (final do arquivo).
-- Pode rodar de novo sem problema: nada é duplicado.
-- ============================================================

-- 1. ADMINS (quem pode entrar no /admin) -----------------------
create table if not exists public.admins (
  email text primary key,
  created_at timestamptz not null default now()
);
alter table public.admins enable row level security;

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (
    select 1 from public.admins
    where lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

drop policy if exists "admins_select" on public.admins;
create policy "admins_select" on public.admins for select to authenticated using (public.is_admin());
drop policy if exists "admins_write" on public.admins;
create policy "admins_write" on public.admins for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- 2. CARROS ------------------------------------------------------
create table if not exists public.carros (
  id uuid primary key default gen_random_uuid(),
  marca text not null,
  modelo text not null,
  versao text not null default '',
  ano int not null default extract(year from now())::int,
  km int not null default 0,
  preco numeric(12,2) not null default 0,
  comb text not null default 'Flex',
  cambio text not null default 'Automático',
  blindado boolean not null default true,
  zero boolean not null default true,
  status text not null default 'disponivel' check (status in ('disponivel','vendido','oculto')),
  cor text not null default '#15161a',
  tipo text not null default 'suv' check (tipo in ('suv','sport')),
  fotos text[] not null default '{}',
  ficha jsonb not null default '[]',
  ordem int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.carros enable row level security;

drop policy if exists "carros_public_read" on public.carros;
create policy "carros_public_read" on public.carros for select to anon, authenticated
  using (status <> 'oculto' or public.is_admin());
drop policy if exists "carros_admin_write" on public.carros;
create policy "carros_admin_write" on public.carros for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- 3. VÍDEOS (seção de vídeos do YouTube) -------------------------
create table if not exists public.videos (
  id uuid primary key default gen_random_uuid(),
  youtube_id text not null,
  tag text not null default 'Review',
  titulo text not null,
  ativo boolean not null default true,
  ordem int not null default 0,
  created_at timestamptz not null default now()
);
alter table public.videos enable row level security;

drop policy if exists "videos_public_read" on public.videos;
create policy "videos_public_read" on public.videos for select to anon, authenticated
  using (ativo or public.is_admin());
drop policy if exists "videos_admin_write" on public.videos;
create policy "videos_admin_write" on public.videos for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- 4. CONFIGURAÇÕES DO SITE (linha única) ------------------------
create table if not exists public.config (
  id int primary key default 1 check (id = 1),
  preco_sob_consulta boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.config enable row level security;
insert into public.config (id) values (1) on conflict (id) do nothing;

drop policy if exists "config_public_read" on public.config;
create policy "config_public_read" on public.config for select to anon, authenticated using (true);
drop policy if exists "config_admin_write" on public.config;
create policy "config_admin_write" on public.config for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- updated_at automático
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists carros_touch on public.carros;
create trigger carros_touch before update on public.carros for each row execute function public.touch_updated_at();
drop trigger if exists config_touch on public.config;
create trigger config_touch before update on public.config for each row execute function public.touch_updated_at();

-- permissões de acesso pela API (a segurança de verdade fica nas políticas acima)
grant usage on schema public to anon, authenticated;
grant select on public.carros, public.videos, public.config to anon, authenticated;
grant select, insert, update, delete on public.carros, public.videos, public.admins to authenticated;
grant update on public.config to authenticated;
grant execute on function public.is_admin() to anon, authenticated;

-- 5. FOTOS (Storage) ----------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', true, 10485760, array['image/webp','image/jpeg','image/png'])
on conflict (id) do update set public = true;

drop policy if exists "fotos_admin_insert" on storage.objects;
create policy "fotos_admin_insert" on storage.objects for insert to authenticated
  with check (bucket_id = 'fotos' and public.is_admin());
drop policy if exists "fotos_admin_update" on storage.objects;
create policy "fotos_admin_update" on storage.objects for update to authenticated
  using (bucket_id = 'fotos' and public.is_admin());
drop policy if exists "fotos_admin_delete" on storage.objects;
create policy "fotos_admin_delete" on storage.objects for delete to authenticated
  using (bucket_id = 'fotos' and public.is_admin());

-- 6. CARGA INICIAL (estoque e vídeos que já estão no site) -------
-- Só roda se as tabelas estiverem vazias.
do $seed$
begin
if not exists (select 1 from public.carros) then
insert into public.carros (marca, modelo, versao, ano, km, preco, comb, cambio, blindado, zero, status, cor, tipo, fotos, ficha, ordem) values
  ('Toyota', 'SW4 SRX Platinum', '2.8 Diesel 4x4 7 lugares', 2026, 0, 559900, 'Diesel', 'Automático', true, true, 'disponivel', '#15161a', 'suv',
   array['assets/cars/sw4-1.jpg','assets/cars/sw4-2.jpg','assets/cars/sw4-3.jpg','assets/cars/sw4-4.jpg','assets/cars/sw4-5.jpg','assets/cars/sw4-6.jpg','assets/cars/sw4-7.jpg','assets/cars/sw4-8.jpg']::text[],
   '[{"k":"Motor","v":"2.8 Turbo Diesel 16V"},{"k":"Potência","v":"204 cv"},{"k":"Torque","v":"51,0 kgfm (500 Nm)"},{"k":"Tração","v":"4x4 integral com reduzida"},{"k":"Câmbio","v":"Automático de 6 marchas"},{"k":"Ocupantes","v":"7 lugares"},{"k":"Tanque","v":"80 litros"},{"k":"Porta-malas","v":"953 L"},{"k":"Comprimento","v":"4,86 m"},{"k":"Entre-eixos","v":"2,75 m"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"3 anos de fábrica"}]'::jsonb, 10),
  ('GWM', 'Wey 07 Dark Edition', '1.5 Turbo PHEV AWD DHT', 2026, 0, 329900, 'Híbrido', 'Automático', true, true, 'disponivel', '#151515', 'suv',
   array['assets/cars/wey07-1.jpg','assets/cars/wey07-2.jpg','assets/cars/wey07-3.jpg','assets/cars/wey07-4.jpg','assets/cars/wey07-5.jpg']::text[],
   '[{"k":"Motor","v":"1.5 Turbo + elétrico (PHEV DHT)"},{"k":"Potência combinada","v":"449 cv"},{"k":"Torque combinado","v":"762 Nm"},{"k":"Tração","v":"AWD integral"},{"k":"Câmbio","v":"Automático DHT"},{"k":"Autonomia elétrica","v":"≈52 km"},{"k":"Bateria","v":"19,09 kWh"},{"k":"Porta-malas","v":"379 L"},{"k":"Comprimento","v":"4,75 m"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"3 anos (bateria 8 anos)"}]'::jsonb, 20),
  ('Denza', 'B5 DM-O', 'Híbrido Plug-in 4x4 · Grupo BYD', 2026, 0, 639900, 'Híbrido', 'Automático', true, true, 'disponivel', '#4a4e54', 'suv',
   array['assets/cars/denza-1.jpg','assets/cars/denza-2.jpg','assets/cars/denza-3.jpg','assets/cars/denza-4.jpg','assets/cars/denza-5.jpg','assets/cars/denza-6.jpg','assets/cars/denza-7.jpg']::text[],
   '[{"k":"Motor","v":"1.5 Turbo + 2 motores elétricos (DM-o)"},{"k":"Potência combinada","v":"505 cv"},{"k":"Torque combinado","v":"760 Nm"},{"k":"Tração","v":"4x4 integral"},{"k":"Câmbio","v":"Automático e-CVT"},{"k":"0-100 km/h","v":"5,8 s"},{"k":"Autonomia elétrica","v":"≈100 km"},{"k":"Bateria","v":"26,6 kWh"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"6 anos"}]'::jsonb, 30),
  ('BYD', 'Song Plus Premium', 'DM-i Híbrido Plug-in', 2026, 0, 249900, 'Híbrido', 'Automático', true, true, 'disponivel', '#111214', 'suv',
   array['assets/cars/byd-songplus-1.jpg','assets/cars/byd-songplus-2.jpg','assets/cars/byd-songplus-3.jpg','assets/cars/byd-songplus-4.jpg','assets/cars/byd-songplus-5.jpg','assets/cars/byd-songplus-6.jpg']::text[],
   '[{"k":"Motor","v":"1.5 Turbo + elétrico (DM-i)"},{"k":"Potência combinada","v":"245 cv"},{"k":"Tração","v":"Dianteira"},{"k":"Câmbio","v":"Automático e-CVT"},{"k":"Autonomia elétrica","v":"≈50 km"},{"k":"Consumo (modo híbrido)","v":"17,8 km/l"},{"k":"Porta-malas","v":"574 L"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"6 anos"}]'::jsonb, 40),
  ('Leapmotor', 'C10', 'Elétrico Range Extender', 2026, 0, 279900, 'Elétrico', 'Automático', true, true, 'disponivel', '#e8e8e6', 'suv',
   array['assets/cars/leapmotor-c10-1.jpg','assets/cars/leapmotor-c10-2.jpg','assets/cars/leapmotor-c10-3.jpg','assets/cars/leapmotor-c10-4.jpg','assets/cars/leapmotor-c10-5.jpg']::text[],
   '[{"k":"Motor","v":"Elétrico com gerador (REEV)"},{"k":"Potência","v":"218 cv"},{"k":"Torque","v":"320 Nm"},{"k":"Tração","v":"Traseira"},{"k":"Autonomia elétrica","v":"≈145 km"},{"k":"Autonomia total (c/ gerador)","v":"≈880 km"},{"k":"Bateria","v":"28,4 kWh"},{"k":"Porta-malas","v":"435 L"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"8 anos (bateria)"}]'::jsonb, 50),
  ('Omoda', '5', '1.5 TGDi HEV Luxury DHT', 2025, 0, 169900, 'Híbrido', 'Automático', false, true, 'disponivel', '#e9e9e7', 'suv',
   array['assets/cars/omoda-5-1.jpg','assets/cars/omoda-5-2.jpg','assets/cars/omoda-5-3.jpg','assets/cars/omoda-5-4.jpg','assets/cars/omoda-5-5.jpg']::text[],
   '[{"k":"Motor","v":"1.5 Turbo Híbrido (HEV DHT)"},{"k":"Potência combinada","v":"197 cv"},{"k":"Torque","v":"275 Nm"},{"k":"Tração","v":"Dianteira"},{"k":"Câmbio","v":"Automático DHT"},{"k":"Consumo","v":"15,8 km/l"},{"k":"Porta-malas","v":"380 L"},{"k":"Comprimento","v":"4,40 m"},{"k":"Garantia","v":"7 anos"}]'::jsonb, 60),
  ('RAM', 'Rampage RT', '2.0 Hurricane Turbo Flex 4x4', 2025, 0, 329900, 'Flex', 'Automático', false, true, 'disponivel', '#1c1d20', 'suv',
   array['assets/cars/ram-rampage-1.jpg','assets/cars/ram-rampage-2.jpg','assets/cars/ram-rampage-3.jpg','assets/cars/ram-rampage-4.jpg','assets/cars/ram-rampage-5.jpg','assets/cars/ram-rampage-6.jpg']::text[],
   '[{"k":"Motor","v":"2.0 Turbo Flex Hurricane"},{"k":"Potência","v":"272 cv (gasolina) / 268 cv (etanol)"},{"k":"Torque","v":"41,8 kgfm"},{"k":"Tração","v":"4x4 com reduzida"},{"k":"Câmbio","v":"Automático de 8 marchas"},{"k":"Caçamba","v":"1,03 m³"},{"k":"Comprimento","v":"5,42 m"},{"k":"Garantia","v":"3 anos de fábrica"}]'::jsonb, 70),
  ('BMW', 'X5 xDrive50e', 'M Sport Híbrido (exemplo ilustrativo)', 2025, 4200, 1189900, 'Híbrido', 'Automático', true, false, 'vendido', '#3a3f46', 'suv',
   array[]::text[],
   '[{"k":"Motor","v":"3.0 reto-6 Turbo + elétrico (PHEV)"},{"k":"Potência combinada","v":"489 cv"},{"k":"Torque","v":"700 Nm"},{"k":"Tração","v":"xDrive integral"},{"k":"Câmbio","v":"Automático Steptronic de 8 marchas"},{"k":"0-100 km/h","v":"4,8 s"},{"k":"Autonomia elétrica","v":"≈110 km"},{"k":"Nível de blindagem","v":"III-A"},{"k":"Garantia","v":"2 anos de fábrica"}]'::jsonb, 80);
end if;
if not exists (select 1 from public.videos) then
insert into public.videos (youtube_id, tag, titulo, ordem) values
  ('MAPJNStmJJ8', 'Review · Blindado', 'Toyota SW4 Diamond 2025 0km BLINDADA | Vale a Pena?', 10),
  ('yBw1hFZleeU', 'Review · Blindado', 'O detalhe dessa Porsche Panamera me pegou de surpresa', 20),
  ('PKHvJIxkuYo', 'Unboxing · Blindado', 'Unboxing de uma BMW M2 blindada — não era o que eu esperava', 30),
  ('VF7D_VGX0G8', 'Review · Blindado', 'Jeep Compass Blackhawk 2.0 Turbo — review real do blindado', 40),
  ('_8Sw-UVqBbw', 'Review completo', 'O melhor nessa faixa? Review completo BMW X5 xDrive50e M Sport', 50),
  ('HS27OGwyDYY', 'Review completo', 'Hummer EV: isso não parece um elétrico — é um tanque de guerra', 60);
end if;
end
$seed$;

-- 7. SEU ACESSO --------------------------------------------------
-- Troque pelo e-mail que você vai usar para entrar no /admin.
-- Para liberar outra pessoa depois, rode esta mesma linha com o e-mail dela.
insert into public.admins (email) values ('SEU_EMAIL_AQUI@gmail.com') on conflict do nothing;
