# -*- coding: utf-8 -*-
"""
Motor de build del gestor. Autocontenido (todas las rutas relativas a esta carpeta).
Lee manifest.json y produce out/site (paginas + assets) y out/qr (codigos QR).
Conserva los IDs (URLs) del manifiesto; genera uno nuevo solo para items sin id.
Uso:  py build_engine.py [--solo-qr]
"""
import json, os, sys, secrets, hashlib, html
import pypdfium2 as pdfium
from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_H

AQUI = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(AQUI, 'config.json'), encoding='utf-8'))
BASE_URL = CFG['base_url'].rstrip('/')
PDFS = os.path.join(AQUI, 'pdfs')
OUT = os.path.join(AQUI, 'out')
SITE = os.path.join(OUT, 'site')
QRDIR = os.path.join(OUT, 'qr')
MANIFEST = os.path.join(AQUI, 'manifest.json')

ANCHO = 1500
CALIDAD = 80
ALFA = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def slug(n=12):
    return ''.join(secrets.choice(ALFA) for _ in range(n))

def hash_pdf(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''):
            h.update(ch)
    return h.hexdigest()[:14]

def render_pdf(ruta, carpeta):
    # cache: si ya existe meta.json en la carpeta, reutiliza (no re-renderiza)
    meta = os.path.join(carpeta, 'meta.json')
    if os.path.isfile(meta):
        try:
            return json.load(open(meta, encoding='utf-8')), True
        except Exception:
            pass
    os.makedirs(carpeta, exist_ok=True)
    doc = pdfium.PdfDocument(ruta)
    paginas = []
    for i, pagina in enumerate(doc):
        wpt, _ = pagina.get_size()
        img = pagina.render(scale=ANCHO / wpt).to_pil().convert('RGB')
        nombre = f'p{i+1:03d}.jpg'
        img.save(os.path.join(carpeta, nombre), 'JPEG', quality=CALIDAD, progressive=True, optimize=True)
        paginas.append({'archivo': nombre, 'w': img.width, 'h': img.height})
    doc.close()
    json.dump(paginas, open(meta, 'w', encoding='utf-8'))
    return paginas, False

ESTADO_DEF = {
    'vigente': ('&#10003;', 'Certificado vigente', 'Documento consultado desde el registro oficial'),
    'proceso': ('&#8635;', 'Certificación en proceso', 'La renovación de este certificado está en trámite'),
    'vencido': ('&#33;', 'Certificado vencido', 'La vigencia de este certificado ha expirado'),
}

def pagina_html(item, asset_dir, paginas):
    n = len(paginas)
    if paginas:
        imgs = '\n'.join(
            f'''<figure class="hoja"><div class="num">Página {i+1} de {n}</div>
<img src="/{asset_dir}/{p['archivo']}" width="{p['w']}" height="{p['h']}" alt="Página {i+1}"
 loading="{'eager' if i == 0 else 'lazy'}" decoding="async" draggable="false"></figure>'''
            for i, p in enumerate(paginas))
    else:
        # sin PDF: bloque vacio con aviso (solo se ve el banner de estado arriba)
        imgs = ('<div class="sinpdf"><div class="ic">&#8635;</div>'
                '<b>Documento en renovación</b>'
                '<span>El certificado actualizado aún no está disponible.<br>Vuelve a escanear el código más adelante.</span></div>')
    estado = item.get('estado', 'vigente')
    if estado not in ESTADO_DEF:
        estado = 'vigente'
    ic, tit, sub = ESTADO_DEF[estado]
    titulo = html.escape(item.get('nombre', 'Certificado') or 'Certificado')
    return f'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=5">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">
<meta name="referrer" content="no-referrer"><meta name="theme-color" content="#0d1b2e">
<title>Certificado · {titulo}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#e9edf3;color:#1c2636;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}}
.cont{{max-width:1060px;margin:0 auto;padding:18px 14px 60px}}
.valido{{display:flex;align-items:center;gap:12px;background:#e8f7ee;border:1px solid #b5e3c6;border-radius:14px;padding:13px 16px;margin-bottom:14px}}
.valido .tick{{width:34px;height:34px;flex:none;border-radius:50%;background:#18a45c;display:grid;place-items:center;color:#fff;font-size:19px;font-weight:700}}
.valido b{{font-size:15.5px;color:#116b3d;display:block}}
.valido span{{font-size:12.5px;color:#4e8a68}}
.valido.estado-proceso{{background:#fdf6e3;border-color:#f0d98a}}
.valido.estado-proceso .tick{{background:#e0a11a}}
.valido.estado-proceso b{{color:#8a6300}}
.valido.estado-proceso span{{color:#9a7b3a}}
.valido.estado-vencido{{background:#fdeaea;border-color:#f2b8b8}}
.valido.estado-vencido .tick{{background:#d23b3b}}
.valido.estado-vencido b{{color:#a11d1d}}
.valido.estado-vencido span{{color:#a85a5a}}
.hoja{{position:relative;background:#fff;border:1px solid #d8dfe9;border-radius:12px;overflow:hidden;margin-bottom:18px;box-shadow:0 4px 18px rgba(28,38,54,.09)}}
.hoja img{{width:100%;height:auto;display:block;pointer-events:none;-webkit-user-drag:none}}
.hoja .num{{position:absolute;top:10px;right:10px;z-index:3;background:rgba(13,27,46,.78);color:#fff;font-size:11.5px;padding:4px 10px;border-radius:20px}}
.sinpdf{{background:#fff;border:1px dashed #d0b978;border-radius:12px;padding:48px 24px;text-align:center;color:#8a6300}}
.sinpdf .ic{{width:56px;height:56px;margin:0 auto 14px;border-radius:50%;background:#fdf6e3;border:1px solid #f0d98a;display:grid;place-items:center;font-size:28px;color:#e0a11a}}
.sinpdf b{{display:block;font-size:16px;color:#7a5b00;margin-bottom:6px}}
.sinpdf span{{font-size:13.5px;color:#9a7b3a;line-height:1.6}}
body.oculto .visor img{{filter:blur(30px)}}
.cortina{{display:none}}
body.oculto .cortina{{display:grid;position:fixed;inset:0;z-index:30;place-items:center;text-align:center;background:rgba(13,27,46,.93);color:#d7e3f4;font-size:15px;padding:30px;line-height:1.6}}
.pie{{text-align:center;font-size:12px;color:#8493ab;line-height:1.8;margin-top:26px}}
@media print{{body{{display:none!important}}}}
</style></head><body>
<main class="cont">
  <div class="valido estado-{estado}"><div class="tick">{ic}</div><div><b>{tit}</b><span>{sub}</span></div></div>
  <section class="visor">
{imgs}
  </section>
  <div class="cortina">El documento se oculta cuando la ventana pierde el foco.<br>Vuelve a esta pestaña para continuar viéndolo.</div>
  <p class="pie">Documento controlado &middot; prohibida su reproducción o distribución no autorizada.<br>
  La validez de este certificado sólo puede confirmarse escaneando el código QR oficial.</p>
</main>
<script>
(function(){{
 ['contextmenu','dragstart','selectstart'].forEach(function(ev){{document.addEventListener(ev,function(e){{e.preventDefault();}},{{passive:false}});}});
 function est(){{document.body.classList.toggle('oculto',document.hidden);}}
 document.addEventListener('visibilitychange',est);
 window.addEventListener('blur',function(){{document.body.classList.add('oculto');}});
 window.addEventListener('focus',function(){{document.body.classList.remove('oculto');}});
 est();
}})();
</script></body></html>'''

PORTADA = '''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>Verificación de certificados</title><style>*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1b2e;color:#e8edf5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;min-height:100vh;display:grid;place-items:center;padding:28px;text-align:center}
.c{max-width:440px}.l{width:66px;height:66px;margin:0 auto 22px;border-radius:16px;background:#182a44;border:1px solid #2c4266;display:grid;place-items:center;font-size:26px}
h1{font-size:20px;margin-bottom:12px;font-weight:600}p{font-size:14.5px;color:#93a7c4;line-height:1.65}</style></head>
<body><div class="c"><div class="l">&#128274;</div><h1>Portal de verificación de certificados</h1>
<p>Para consultar el certificado de un equipo, escanee el código QR adherido al equipo o publicado en el cuadro oficial.<br><br>
Este portal no publica listados: cada certificado sólo es accesible mediante su código único.</p></div></body></html>'''
P404 = PORTADA.replace('Portal de verificación de certificados', 'Certificado no encontrado').replace(
    'Para consultar el certificado de un equipo, escanee el código QR adherido al equipo o publicado en el cuadro oficial.',
    'El código consultado no corresponde a ningún certificado vigente del registro.')

def gen_qr(url, dst):
    q = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=20, border=2)
    q.add_data(url); q.make(fit=True)
    img = q.make_image(fill_color=(16, 28, 46), back_color=(255, 255, 255))
    img.save(dst)

def main(solo_qr=False):
    import shutil
    manifest = json.load(open(MANIFEST, encoding='utf-8'))

    # asignar id a items nuevos y persistirlo
    usados = {m['id'] for m in manifest if m.get('id')}
    cambiado = False
    for m in manifest:
        if not m.get('id'):
            s = slug()
            while s in usados:
                s = slug()
            m['id'] = s; usados.add(s); cambiado = True
    for m in manifest:
        m['url'] = f"{BASE_URL}/v/{m['id']}"

    os.makedirs(os.path.join(SITE, 'v'), exist_ok=True)
    os.makedirs(os.path.join(SITE, 'a'), exist_ok=True)
    os.makedirs(QRDIR, exist_ok=True)

    # 1) render de cada PDF unico (con CACHE: reutiliza los ya convertidos).
    #    Si el PDF fuente no esta (paquete liviano), usa la 'huella' guardada (pdf_hash)
    #    para reutilizar directamente las imagenes ya convertidas del cache.
    render_map = {}
    hashes_usados = set()
    hash_conocido = {m['pdf']: m.get('pdf_hash') for m in manifest if m.get('pdf') and m.get('pdf_hash')}
    if not solo_qr:
        unicos = sorted({m['pdf'] for m in manifest if m.get('pdf')})
        print(f"Preparando {len(unicos)} PDFs (reutiliza los que no cambiaron)...", flush=True)
        nuevos = 0
        for i, rel in enumerate(unicos, 1):
            ruta = os.path.join(PDFS, rel)
            if os.path.isfile(ruta):                      # hay PDF fuente -> convierte/reutiliza
                h = hash_pdf(ruta)
                paginas, cacheado = render_pdf(ruta, os.path.join(SITE, 'a', h))
            else:                                         # no hay fuente -> usar huella + cache
                h = hash_conocido.get(rel)
                meta = os.path.join(SITE, 'a', h or '_', 'meta.json')
                if h and os.path.isfile(meta):
                    paginas, cacheado = json.load(open(meta, encoding='utf-8')), True
                else:
                    print(f"  AVISO: sin PDF ni cache para {rel[:44]} -> quedara sin documento", flush=True)
                    render_map[rel] = (None, None)
                    continue
            hashes_usados.add(h)
            render_map[rel] = (f'a/{h}', paginas)
            for m in manifest:
                if m.get('pdf') == rel:
                    m['pdf_hash'] = h                     # guardar la huella en el manifest
            if not cacheado:
                nuevos += 1
                print(f"  convertido: {rel[:48]} ({len(paginas)}p)", flush=True)
        print(f"  {nuevos} convertidos, {len(unicos)-nuevos} reutilizados del cache", flush=True)

    # 2) paginas + QR  (regenera todas las paginas HTML -> rapido)
    if not solo_qr:
        shutil.rmtree(os.path.join(SITE, 'v'), ignore_errors=True)
        os.makedirs(os.path.join(SITE, 'v'), exist_ok=True)
    for m in manifest:
        if not solo_qr:
            info = render_map.get(m['pdf']) if m.get('pdf') else None
            if info and info[1] is not None:
                carpeta_rel, paginas = info
            else:
                carpeta_rel, paginas = None, []   # sin PDF (o sin cache) -> pagina solo con banner
            m['paginas'] = len(paginas)
            d = os.path.join(SITE, 'v', m['id'])
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(pagina_html(m, carpeta_rel, paginas))
        gen_qr(m['url'], os.path.join(QRDIR, m['id'] + '.png'))

    # 3) limpiar carpetas de imagenes que ya no usa ningun certificado
    if not solo_qr:
        adir = os.path.join(SITE, 'a')
        for h in os.listdir(adir):
            if h not in hashes_usados:
                shutil.rmtree(os.path.join(adir, h), ignore_errors=True)

    if not solo_qr:
        open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(PORTADA)
        open(os.path.join(SITE, '404.html'), 'w', encoding='utf-8').write(P404)
        open(os.path.join(SITE, '_headers'), 'w', encoding='utf-8').write(
            '/*\n  X-Robots-Tag: noindex, nofollow, noimageindex\n  Referrer-Policy: no-referrer\n  X-Frame-Options: DENY\n  X-Content-Type-Options: nosniff\n')
        open(os.path.join(SITE, 'robots.txt'), 'w', encoding='utf-8').write('User-agent: *\nDisallow: /\n')

    json.dump(manifest, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"OK: {len(manifest)} certificados" + ("" if solo_qr else f" | sitio en {SITE}"), flush=True)

if __name__ == '__main__':
    main(solo_qr='--solo-qr' in sys.argv)
