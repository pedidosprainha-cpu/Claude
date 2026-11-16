"""Páginas públicas: página de captura de cada campanha e aviso de privacidade."""
from html import escape

from . import criativos, db
from .leads import TEXTO_CONSENTIMENTO

_ESTILO = """
:root{--fundo:#f6f7f9;--cartao:#fff;--texto:#14161a;--suave:#5d6470;--borda:#e3e6ea;--marca:#0e7a5f;--marca-texto:#fff}
@media (prefers-color-scheme:dark){:root{--fundo:#0f1115;--cartao:#181b21;--texto:#eef0f3;--suave:#9aa3ae;--borda:#2a2f37;--marca:#34c99a;--marca-texto:#06231b}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:560px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:1.75rem;line-height:1.2;margin:0 0 12px;text-wrap:balance}
p{margin:0 0 14px}.suave{color:var(--suave)}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:14px;padding:18px;margin:18px 0}
.botao{display:block;width:100%;text-align:center;background:var(--marca);color:var(--marca-texto);border:0;border-radius:12px;
padding:15px 18px;font:600 1.05rem system-ui,sans-serif;text-decoration:none;cursor:pointer}
label{display:block;font-size:.9rem;margin:10px 0 4px}input[type=text],input[type=email],input[type=tel]{width:100%;padding:12px;
border:1px solid var(--borda);border-radius:10px;background:var(--fundo);color:var(--texto);font-size:1rem}
.consent{display:flex;gap:10px;align-items:flex-start;font-size:.85rem;color:var(--suave);margin:14px 0}
.consent input{margin-top:4px;width:18px;height:18px;flex:none}
footer{font-size:.8rem;color:var(--suave);margin-top:28px}footer a{color:inherit}
#ok{display:none;font-weight:600;color:var(--marca)}#erro{color:#c62828;font-size:.9rem}
"""


def captura(campanha_id):
    c = db.um("SELECT * FROM campanhas WHERE id = ?", (campanha_id,))
    if not c:
        return None
    p = db.um("SELECT * FROM produtos WHERE id = ?", (c["produto_id"],))
    cr = db.um("SELECT * FROM criativos WHERE id = ?", (c["criativo_id"],))
    nome = escape(p["nome"].replace(" (exemplo)", ""))
    publico = escape(p.get("publico") or "")
    beneficio = escape(p.get("beneficio") or "")
    cta = escape(criativos.CTAS.get(cr["cta"], "Saiba mais"))
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(cr['titulo'])}</title>
<style>{_ESTILO}</style></head><body><main>
<h1>{escape(cr['titulo'])}</h1>
<p>{escape(cr['texto'])}</p>
<div class="cartao">
  <p><strong>O que é:</strong> {nome}</p>
  {f'<p><strong>O que você aprende:</strong> {beneficio}.</p>' if beneficio else ''}
  {f'<p><strong>Para quem é:</strong> {publico}.</p>' if publico else ''}
  <p class="suave">Você será levado à página oficial do produto, onde pode ver todos os detalhes antes de decidir.</p>
  <a class="botao" id="ir" href="/ir/{campanha_id}">{cta}</a>
</div>
<div class="cartao">
  <p><strong>Quer receber novidades sobre o assunto?</strong></p>
  <form id="form">
    <label for="nome">Nome</label><input id="nome" type="text" autocomplete="given-name" maxlength="80">
    <label for="email">E-mail</label><input id="email" type="email" autocomplete="email" maxlength="120">
    <label for="zap">WhatsApp (opcional)</label><input id="zap" type="tel" autocomplete="tel" maxlength="20">
    <div class="consent"><input id="aceito" type="checkbox"><label for="aceito" style="margin:0">{escape(TEXTO_CONSENTIMENTO)}</label></div>
    <button class="botao" type="submit">Quero receber</button>
    <p id="erro"></p><p id="ok">Pronto! Contato recebido.</p>
  </form>
</div>
<footer>Esta página é mantida por um afiliado do produto. <a href="/privacidade">Privacidade e seus dados</a>.</footer>
</main>
<script>
(function(){{
  var c={campanha_id},k="mv_v",v;
  try{{v=localStorage.getItem(k);if(!v){{v=(crypto.randomUUID?crypto.randomUUID():String(Math.random()).slice(2));localStorage.setItem(k,v);}}}}catch(e){{v=String(Math.random()).slice(2);}}
  function ev(t){{fetch("/api/v/evento",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{v:v,c:c,tipo:t}}),keepalive:true}}).catch(function(){{}});}}
  ev("visita");
  var rolou=false;addEventListener("scroll",function(){{if(!rolou&&scrollY+innerHeight>=document.body.scrollHeight*0.5){{rolou=true;ev("rolou_50");}}}},{{passive:true}});
  setTimeout(function(){{ev("ficou_30s");}},30000);
  document.getElementById("ir").href="/ir/"+c+"?v="+encodeURIComponent(v);
  document.getElementById("form").addEventListener("submit",function(e){{
    e.preventDefault();var erro=document.getElementById("erro");erro.textContent="";
    fetch("/api/v/cadastro",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{
      v:v,c:c,nome:document.getElementById("nome").value,email:document.getElementById("email").value,
      whatsapp:document.getElementById("zap").value,consentimento:document.getElementById("aceito").checked}})}})
    .then(function(r){{return r.json().then(function(d){{if(!r.ok)throw new Error(d.detail||"Erro");}});}})
    .then(function(){{document.getElementById("form").querySelectorAll("input,button").forEach(function(x){{x.disabled=true;}});document.getElementById("ok").style.display="block";}})
    .catch(function(x){{erro.textContent=x.message;}});
  }});
}})();
</script></body></html>"""


def privacidade():
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Privacidade</title>
<style>{_ESTILO}</style></head><body><main>
<h1>Privacidade e seus dados</h1>
<p>Esta página é mantida por um afiliado. Coletamos apenas o que você informa no formulário (nome, e-mail e
WhatsApp) e só com o seu consentimento, para enviar conteúdos e ofertas sobre o assunto da página.</p>
<p>Também registramos, sem identificar você, como a página é usada (visita, leitura, clique na oferta), para
melhorar os anúncios.</p>
<p>Não vendemos seus dados. Você pode pedir a exclusão a qualquer momento respondendo qualquer mensagem
nossa ou pelo contato do responsável.</p>
<p class="suave">Base legal: consentimento (art. 7º, I, da LGPD).</p>
</main></body></html>"""
