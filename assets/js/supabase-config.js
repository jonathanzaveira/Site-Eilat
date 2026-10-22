/* ============================================================
   CONEXÃO COM O SUPABASE (usado pelo site e pelo /admin)
   Cole aqui os dois valores do seu projeto Supabase:
   Project Settings > API Keys (ou Data API)
   - url: Project URL  (ex: https://abcdefgh.supabase.co)
   - key: Publishable key (sb_publishable_...) ou a "anon public" antiga
   Essa chave é pública por natureza: quem protege os dados são as
   regras criadas pelo setup.sql. NUNCA cole aqui a secret/service_role.
   Enquanto estiver vazio, o site continua mostrando o estoque fixo
   que já está dentro do index.html.
   ============================================================ */
window.EILAT_SUPABASE = {
  url: '',
  key: ''
};
