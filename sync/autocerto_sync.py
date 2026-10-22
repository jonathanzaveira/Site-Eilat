"""
Espelha o estoque da AutoCerto no banco do site (Supabase).

Roda sozinho pelo GitHub Actions (.github/workflows/sincronizar-autocerto.yml).
Variáveis de ambiente (cadastradas em Settings > Secrets and variables > Actions):
  AUTOCERTO_USERNAME, AUTOCERTO_PASSWORD   usuário e senha da API AutoCerto
  SUPABASE_URL                             ex: https://abcdefgh.supabase.co
  SUPABASE_SERVICE_KEY                     chave secreta (sb_secret_... ou service_role)
Opcionais:
  AUTOCERTO_URL       padrão https://integracao.autocerto.com
  DIAS_VENDIDO        quantos dias um carro vendido continua aparecendo com o selo (padrão 15)

Regras:
  - carro novo na AutoCerto entra no site (no topo da lista)
  - carro alterado na AutoCerto é atualizado (dados e fotos)
  - carro que sumiu da AutoCerto vira "Vendido"; depois de DIAS_VENDIDO dias fica oculto
  - carro que volta para a AutoCerto volta a ficar disponível
  - ordem, ocultar e ficha técnica editada no painel nunca são sobrescritos
  - placa, renavam e chassi são descartados e nunca vão para o banco
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

AC_URL = os.environ.get("AUTOCERTO_URL", "https://integracao.autocerto.com").rstrip("/")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DIAS_VENDIDO = int(os.environ.get("DIAS_VENDIDO", "15"))

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# ------------------------------------------------------------------ nomes
SIGLAS = {
    "BMW", "GWM", "BYD", "RAM", "VW", "HR-V", "WR-V", "CR-V", "ZR-V", "GTDI", "CD", "CS", "GLI", "DSG", "PDK", "CDI", "XRX", "TCI", "MIVEC", "HPE", "AWC", "DI", "VTEC", "JAC", "GAC", "MG", "GM", "AMG",
    "GLA", "GLB", "GLC", "GLE", "GLS", "EQA", "EQB", "EQE", "EQS", "CLA", "SUV",
    "PHEV", "HEV", "MHEV", "REEV", "EV", "BEV", "AWD", "FWD", "RWD", "DHT", "DCT", "CVT", "AT", "MT",
    "TDI", "TSI", "TFSI", "TGDI", "GDI", "MPI", "CRDI", "VVT", "VVTI", "D-4D", "DM-I", "DM-P", "DM-O",
    "GT", "GTS", "GTI", "RS", "RT", "R/T", "SRX", "SRV", "SR", "GR", "GR-S", "GS", "HSE", "SE", "SV",
    "XLT", "XLS", "XL", "LT", "LTZ", "LX", "EX", "EXL", "GLX", "XRE", "XEI", "XE", "TRD", "TRX", "SRT",
    "ST", "SX", "LS", "S", "M", "X", "R", "V6", "V8", "I4", "I6", "KW", "CV", "TB", "AUT", "MEC",
}
MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "com"}
MODELOS_ESP = {"IX": "iX", "IX1": "iX1", "IX2": "iX2", "IX3": "iX3", "I4": "i4", "I5": "i5", "I7": "i7"}
ESPECIAIS = {"VVT-IE": "VVT-iE", "VVT-I": "VVT-i", "I-VTEC": "i-VTEC", "IFLEX": "iFlex", "AUTOMATICO": "Automático",
             "ECOBOOST": "EcoBoost", "SELECTSHIFT": "SelectShift", "TWINPOWER": "TwinPower", "KW": "kW",
             "HPE-S": "HPE-S", "S-AWC": "S-AWC", "AUT": "Aut.", "AUT.": "Aut.", "MEC": "Mec.", "MEC.": "Mec."}


def _palavra(w, i, campo):
    up = w.upper()
    if campo == "modelo" and up in MODELOS_ESP:
        return MODELOS_ESP[up]
    if up in ESPECIAIS:
        return ESPECIAIS[up]
    m = re.match(r"^([XS])DRIVE(\d*)([A-Z]*)$", up)
    if m:
        return m.group(1).lower() + "Drive" + m.group(2) + m.group(3).lower()
    if up in SIGLAS:
        return up
    if any(ch.isdigit() for ch in w):
        return up
    if i > 0 and w.lower() in MINUSCULAS:
        return w.lower()
    if "-" in w and not w.startswith("-"):
        return "-".join(_palavra(p, 1, campo) for p in w.split("-"))
    if len(w) == 1:
        return up
    return w[:1].upper() + w[1:].lower()


def bonito(texto, campo=""):
    texto = re.sub(r"\s+", " ", (texto or "").strip())
    return " ".join(_palavra(w, i, campo) for i, w in enumerate(texto.split(" "))) if texto else ""


def modelo_bonito(marca, modelo):
    m = bonito(modelo, "modelo")
    if (marca or "").upper() in ("BMW", "MERCEDES-BENZ"):  # 320I -> 320i, GLE 450D -> GLE 450d
        m = re.sub(r"(\d)([A-Z])\b", lambda x: x.group(1) + x.group(2).lower(), m)
    return m


COMBUSTIVEL = {"gasolina e elétrico": "Híbrido", "gasolina e eletrico": "Híbrido", "híbrido": "Híbrido",
               "diesel e elétrico": "Híbrido", "flex e elétrico": "Híbrido"}
CORES = {"preto": "#15161a", "preta": "#15161a", "branco": "#e9e9e7", "branca": "#e9e9e7", "cinza": "#4a4e54",
         "prata": "#9a9da2", "grafite": "#3a3f46", "azul": "#1f3a5f", "vermelho": "#6b1a1a", "vermelha": "#6b1a1a",
         "verde": "#2f4a3a", "bege": "#b8a98c", "marrom": "#4a3426", "dourado": "#8a7442", "laranja": "#a4461c",
         "amarelo": "#a88a1f", "vinho": "#4a1420"}


def mapear(v):
    """Converte um veículo da AutoCerto para o formato da tabela carros (sem campos sensíveis)."""
    opc = [o.get("Descricao", "").strip() for o in (v.get("Opcionais") or []) if o.get("Descricao")]
    blindado = any(re.search(r"blind", o, re.I) for o in opc) or bool(re.search(r"blind", v.get("Versao") or "", re.I))
    fotos = [f["URL"].replace("http://", "https://", 1)
             for f in sorted(v.get("Fotos") or [], key=lambda f: (f.get("Posicao") or 999, f.get("Codigo") or 0))
             if f.get("URL")]
    comb = (v.get("Combustivel") or "").strip()
    cor = (v.get("Cor") or "").strip()
    categoria = (v.get("Categoria") or "").strip()
    return {
        "autocerto_id": int(v["Codigo"]),
        "origem": "autocerto",
        "marca": bonito(v.get("Marca")),
        "modelo": modelo_bonito(v.get("Marca"), v.get("Modelo")),
        "versao": bonito(v.get("Versao")),
        "ano": int(v.get("AnoModelo") or v.get("AnoFabricacao") or 0),
        "km": int(v.get("Km") or 0),
        "preco": float(v.get("Preco") or v.get("PrecoClassificados") or 0),
        "comb": COMBUSTIVEL.get(comb.lower(), comb or "Flex"),
        "cambio": (v.get("Cambio") or "Automático").strip(),
        "blindado": blindado,
        "zero": bool(v.get("ZeroKm")),
        "cor": CORES.get(cor.lower().split(" ")[0], "#15161a") if cor else "#15161a",
        "tipo": "sport" if categoria.lower() in ("esportivo", "coupé", "coupe", "conversível") else "suv",
        "categoria": categoria,
        "fotos": fotos,
        "opcionais": sorted({o for o in opc if not re.fullmatch(r"blindado", o, re.I)}, key=str.lower),
    }


def ficha_inicial(v, row):
    """Ficha técnica criada só na primeira vez; depois quem manda é o painel."""
    itens = []
    if v.get("Cor"):
        itens.append({"k": "Cor", "v": bonito(v["Cor"])})
    if row["categoria"]:
        itens.append({"k": "Carroceria", "v": bonito(row["categoria"])})
    if v.get("Portas"):
        itens.append({"k": "Portas", "v": str(v["Portas"])})
    if v.get("AnoFabricacao") and v.get("AnoModelo") and v["AnoFabricacao"] != v["AnoModelo"]:
        itens.append({"k": "Ano de fabricação", "v": str(v["AnoFabricacao"])})
    if row["blindado"]:
        itens.append({"k": "Nível de blindagem", "v": "III-A"})
    return itens


def assinatura(row):
    return hashlib.sha1(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ------------------------------------------------------------------ HTTP
def _tentar(fn, nome, tentativas=3):
    ultimo = None
    for n in range(tentativas):
        try:
            return fn()
        except requests.RequestException as e:
            ultimo = e
            time.sleep(3 * (n + 1))
    raise RuntimeError(f"{nome}: {ultimo}")


def autocerto_estoque():
    user, pwd = os.environ.get("AUTOCERTO_USERNAME"), os.environ.get("AUTOCERTO_PASSWORD")
    if not user or not pwd:
        raise RuntimeError("Faltam os secrets AUTOCERTO_USERNAME e AUTOCERTO_PASSWORD")
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)

    def token():
        r = s.post(AC_URL + "/oauth/token", data={"grant_type": "password", "username": user, "password": pwd}, timeout=30)
        if r.status_code == 403 and "Access Denied" in r.text:
            raise RuntimeError("AutoCerto bloqueou a conexão (firewall Akamai, 403 Access Denied)")
        if r.status_code != 200:
            raise RuntimeError(f"Login na AutoCerto falhou (HTTP {r.status_code}): {r.text[:200]}")
        return r.json()["access_token"]

    tk = _tentar(token, "Token AutoCerto")

    def estoque():
        r = s.get(AC_URL + "/api/Veiculo/ObterEstoque", headers={"Authorization": "Bearer " + tk}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"ObterEstoque falhou (HTTP {r.status_code}): {r.text[:200]}")
        return r.json()

    dados = _tentar(estoque, "Estoque AutoCerto")
    if not isinstance(dados, list):
        raise RuntimeError("Resposta inesperada do ObterEstoque")
    return dados


class Supa:
    def __init__(self):
        if not SB_URL or not SB_KEY:
            raise RuntimeError("Faltam os secrets SUPABASE_URL e SUPABASE_SERVICE_KEY")
        self.s = requests.Session()
        self.s.headers.update({"apikey": SB_KEY, "Content-Type": "application/json"})
        if SB_KEY.count(".") == 2:  # chave antiga em formato JWT
            self.s.headers["Authorization"] = "Bearer " + SB_KEY

    def req(self, method, path, **kw):
        def go():
            r = self.s.request(method, SB_URL + "/rest/v1/" + path, timeout=60, **kw)
            if r.status_code >= 400:
                raise RuntimeError(f"Supabase {method} {path.split('?')[0]} HTTP {r.status_code}: {r.text[:300]}")
            return r.json() if r.text.strip() else None
        return _tentar(go, "Supabase")


# ------------------------------------------------------------------ sincronização
def sincronizar():
    db = Supa()
    agora = datetime.now(timezone.utc)
    try:
        feed = autocerto_estoque()
        atuais = db.req("GET", "carros?select=id,autocerto_id,status,vendido_em,ordem,autocerto_modificado,origem")
        por_ac = {c["autocerto_id"]: c for c in atuais if c["autocerto_id"] is not None}
        ativos = [c for c in por_ac.values() if c["status"] != "vendido" and not c["vendido_em"]]

        # trava de segurança: estoque vazio ou queda brusca costuma ser falha da API, não venda em massa
        if not feed:
            raise RuntimeError("A AutoCerto devolveu o estoque vazio; nada foi alterado por segurança")
        if len(ativos) >= 10 and len(feed) < 0.5 * len(ativos):
            raise RuntimeError(f"A AutoCerto devolveu {len(feed)} carros contra {len(ativos)} no site; queda grande demais, nada foi alterado por segurança")

        novos, alterados, voltaram = [], [], []
        menor_ordem = min([c["ordem"] for c in atuais] or [10])
        vistos = set()
        # novos entram no topo, os cadastrados mais recentemente primeiro
        for v in sorted(feed, key=lambda x: x.get("DataCadastro") or "", reverse=False):
            row = mapear(v)
            vistos.add(row["autocerto_id"])
            sig = assinatura(row)
            atual = por_ac.get(row["autocerto_id"])
            if not atual:
                menor_ordem -= 10
                novos.append(dict(row, autocerto_modificado=sig, ficha=ficha_inicial(v, row), status="disponivel", ordem=menor_ordem))
            else:
                if atual["autocerto_modificado"] != sig:
                    alterados.append(dict(row, autocerto_modificado=sig))
                if atual["vendido_em"]:
                    voltaram.append(atual["id"])

        if novos:
            for i in range(0, len(novos), 100):
                db.req("POST", "carros", data=json.dumps(novos[i:i + 100]), headers={"Prefer": "return=minimal"})
        if alterados:
            for i in range(0, len(alterados), 100):
                db.req("POST", "carros?on_conflict=autocerto_id", data=json.dumps(alterados[i:i + 100]),
                       headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
        if voltaram:
            db.req("PATCH", "carros?id=in.(" + ",".join(voltaram) + ")&status=in.(vendido,oculto)",
                   data=json.dumps({"status": "disponivel", "vendido_em": None}), headers={"Prefer": "return=minimal"})
            db.req("PATCH", "carros?id=in.(" + ",".join(voltaram) + ")",
                   data=json.dumps({"vendido_em": None}), headers={"Prefer": "return=minimal"})

        # saíram da AutoCerto: vendidos
        sairam = [c["id"] for c in por_ac.values() if c["autocerto_id"] not in vistos and not c["vendido_em"]]
        if sairam:
            db.req("PATCH", "carros?id=in.(" + ",".join(sairam) + ")&status=eq.disponivel",
                   data=json.dumps({"status": "vendido"}), headers={"Prefer": "return=minimal"})
            db.req("PATCH", "carros?id=in.(" + ",".join(sairam) + ")",
                   data=json.dumps({"vendido_em": agora.isoformat()}), headers={"Prefer": "return=minimal"})

        # vendidos há mais de DIAS_VENDIDO dias saem do site
        limite = (agora - timedelta(days=DIAS_VENDIDO)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.req("PATCH", f"carros?origem=eq.autocerto&status=eq.vendido&vendido_em=lt.{limite}",
               data=json.dumps({"status": "oculto"}), headers={"Prefer": "return=minimal"})

        # na primeira sincronização, os carros de exemplo cadastrados à mão saem do site (ficam ocultos, não apagados)
        conf = db.req("GET", "config?select=seed_ocultado&id=eq.1")
        if conf and not conf[0]["seed_ocultado"]:
            db.req("PATCH", "carros?origem=eq.seed", data=json.dumps({"status": "oculto"}), headers={"Prefer": "return=minimal"})

        msg = f"{len(feed)} carros na AutoCerto · {len(novos)} novos · {len(alterados)} atualizados · {len(sairam)} vendidos · {len(voltaram)} voltaram"
        db.req("PATCH", "config?id=eq.1", data=json.dumps({"sync_em": agora.isoformat(), "sync_ok": True, "sync_msg": msg, "seed_ocultado": True}),
               headers={"Prefer": "return=minimal"})
        print("OK:", msg)
        return 0
    except Exception as e:  # registra o erro para aparecer no painel e falha o job (o GitHub avisa por e-mail)
        msg = str(e)[:500]
        print("ERRO:", msg, file=sys.stderr)
        try:
            db.req("PATCH", "config?id=eq.1", data=json.dumps({"sync_em": agora.isoformat(), "sync_ok": False, "sync_msg": msg}),
                   headers={"Prefer": "return=minimal"})
        except Exception as e2:
            print("Também não consegui registrar o erro no banco:", e2, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(sincronizar())
