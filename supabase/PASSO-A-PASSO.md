# Painel do site Eilat Motors: como ativar

Tempo total: uns 25 minutos. O site continua no GitHub Pages e no mesmo domínio. Enquanto o passo 4 não for feito, o site funciona exatamente como hoje, com o estoque fixo.

## 1. Criar o projeto no Supabase

1. Entre em supabase.com e crie uma conta (pode usar o login do GitHub).
2. Clique em **New project**. Nome: `eilat-site`. Região: **South America (São Paulo)**. Crie uma senha do banco e guarde.
3. Espere o projeto terminar de criar (1 a 2 minutos).

## 2. Criar o banco

1. No menu da esquerda, abra **SQL Editor**.
2. Abra o arquivo `supabase/setup.sql`, copie tudo e cole no editor.
3. No final do arquivo, troque `SEU_EMAIL_AQUI@gmail.com` pelo e-mail que você vai usar para entrar no painel.
4. Clique em **Run**. Deve aparecer "Success". Isso cria as tabelas, as regras de segurança, a pasta de fotos e já carrega os 8 carros e os 6 vídeos que estão no site hoje (os 8 carros saem do ar sozinhos na primeira sincronização com a AutoCerto).

## 3. Criar seu login

1. Menu **Authentication** > **Users** > **Add user** > **Create new user**.
2. Use o mesmo e-mail do passo 2, crie uma senha e marque **Auto Confirm User**.
3. Recomendado: em **Authentication** > **Sign In / Providers**, desligue **Allow new users to sign up**. Assim ninguém cria conta por conta própria (mesmo que crie, não teria acesso a nada, mas fica mais limpo).

## 4. Ligar o site ao banco

1. Menu **Project Settings** > **API Keys** (em alguns projetos aparece como **Data API**).
2. Copie a **Project URL** e a **Publishable key** (começa com `sb_publishable_`). Se só aparecer a chave antiga, use a **anon public**.
3. No GitHub, abra `assets/js/supabase-config.js`, clique no lápis para editar e cole:

```js
window.EILAT_SUPABASE = {
  url: 'https://SEU-PROJETO.supabase.co',
  key: 'sb_publishable_...'
};
```

4. Clique em **Commit changes**. Em 1 a 2 minutos o GitHub Pages publica.

Nunca cole a chave **secret** ou **service_role** nesse arquivo.

## 5. Ligar o espelhamento com a AutoCerto

O robô roda no próprio GitHub, a cada 30 minutos, e copia o estoque da AutoCerto para o site.

1. No Supabase, em **Project Settings** > **API Keys**, copie a **Secret key** (começa com `sb_secret_`). Se só aparecer a chave antiga, use a **service_role**. Essa chave dá acesso total ao banco: ela vai só no GitHub, como secret, e nunca em arquivo do site.
2. No GitHub, abra o repositório **Site-Eilat** > **Settings** > **Secrets and variables** > **Actions** > **New repository secret** e crie estes 4, um de cada vez:

| Name | Secret |
|---|---|
| `AUTOCERTO_USERNAME` | usuário da API AutoCerto (o mesmo do Swagger) |
| `AUTOCERTO_PASSWORD` | senha da API AutoCerto |
| `SUPABASE_URL` | a Project URL do passo 4 |
| `SUPABASE_SERVICE_KEY` | a Secret key deste passo |

3. Vá na aba **Actions**. Se aparecer um aviso pedindo para habilitar os workflows, clique em habilitar.
4. Clique em **Sincronizar estoque AutoCerto** > **Run workflow** > **Run workflow**. Em 1 minuto deve aparecer um check verde.
5. Abra o site: o estoque já é o da AutoCerto. No painel, o topo da aba Estoque mostra quando foi a última sincronização.

Se aparecer um X vermelho, clique nele e abra o passo **Sincronizar** para ver o motivo. O mais provável é o firewall da AutoCerto (Akamai) bloquear o servidor do GitHub; nesse caso, encaminhe a mensagem para o suporte da AutoCerto pedindo liberação. O GitHub também avisa por e-mail quando uma sincronização falha.

### Como o espelhamento funciona

- Carro novo na AutoCerto: entra no site no topo da lista.
- Preço, km, fotos ou opcionais alterados na AutoCerto: atualizam no site.
- Carro que sai do estoque da AutoCerto: vira **Vendido** no site, com o selo e o botão "Avise-me", e some depois de 15 dias.
- Carro que volta para a AutoCerto: volta a ficar disponível.
- No painel, carros da AutoCerto aparecem com a etiqueta **AUTOCERTO**: dados e fotos ficam travados (edite na AutoCerto), mas você pode ocultar, mudar a ordem e editar a ficha técnica, e o robô respeita essas escolhas.
- Placa, chassi e renavam são descartados e nunca vão para o site.
- Trava de segurança: se a AutoCerto devolver o estoque vazio ou com menos da metade dos carros, o robô não mexe em nada e registra o erro (evita marcar tudo como vendido por uma falha da AutoCerto).

## 6. Usar

Acesse **eilatbarra.com.br/admin** e entre com o e-mail e senha do passo 3.

- **Estoque**: novo veículo, editar, fotos (subir várias, arrastar para ordenar, estrela para virar capa, X para apagar), situação Disponível / Vendido / Oculto, ficha técnica, e arrastar a lista para mudar a ordem no site.
- **Vídeos**: colar link do YouTube, editar etiqueta e título, ligar e desligar, reordenar.
- **Configurações**: preço sob consulta liga e desliga para o site todo, liberar acesso para outras pessoas, trocar senha.

Tudo que é salvo no painel aparece no site na hora, sem precisar mexer no GitHub.

## Liberar acesso para alguém da equipe

1. Crie o usuário da pessoa no Supabase (passo 3, com o e-mail dela).
2. No painel, em **Configurações** > **Quem pode acessar o painel**, adicione o e-mail.

## Observações

- Vendido x Excluir: se o carro foi vendido, use a situação **Vendido** (ele aparece com o selo e o botão "Avise-me"). Excluir apaga de vez, com as fotos.
- Fotos do iPhone em HEIC podem não subir em alguns navegadores. Se acontecer, o painel avisa; exporte como JPG.
- O plano gratuito do Supabase pausa o projeto depois de 7 dias sem nenhum acesso. Com o site no ar recebendo visitas isso não acontece; se acontecer, o site mostra o estoque fixo e basta entrar no Supabase e clicar em **Restore**.
