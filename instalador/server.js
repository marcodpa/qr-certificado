// Gestor de certificados — servidor local. No expone nada a internet: solo escucha en 127.0.0.1.
const fs0 = require('fs');
const path0 = require('path');
// Cualquier error de arranque se guarda en un archivo y se muestra, para no perderlo.
function registrarError(msg) {
  try { fs0.writeFileSync(path0.join(__dirname, 'ERROR-arranque.txt'), new Date().toISOString() + '\n' + msg + '\n'); } catch {}
  console.error('\n============================================================');
  console.error('  NO SE PUDO INICIAR EL GESTOR');
  console.error('============================================================');
  console.error(msg);
  console.error('(Este error se guardó también en ERROR-arranque.txt)\n');
}
process.on('uncaughtException', (e) => { registrarError((e && e.stack) || String(e)); process.exitCode = 1; });

const express = require('express');
const multer = require('multer');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const AQUI = __dirname;
const MANIFEST = path.join(AQUI, 'manifest.json');
const PDFS = path.join(AQUI, 'pdfs');
const QRDIR = path.join(AQUI, 'out', 'qr');
const PENDING = path.join(AQUI, '.pending');
const CFG = JSON.parse(fs.readFileSync(path.join(AQUI, 'config.json'), 'utf8'));
const PORT = 4599;

// Resuelve un python.exe REAL (el comando 'py' suele ser un alias de la Store que spawn no ejecuta bien)
function buscarPython() {
  const cands = [];
  if (CFG.python) cands.push(CFG.python);
  // carpetas donde suele instalarse Python; se escanean subcarpetas buscando python.exe
  const bases = [];
  const la = process.env.LOCALAPPDATA, pf = process.env.ProgramFiles, pf86 = process.env['ProgramFiles(x86)'];
  if (la) { bases.push(path.join(la, 'Python'), path.join(la, 'Programs', 'Python')); }
  if (pf) bases.push(path.join(pf, 'Python'));
  if (pf86) bases.push(path.join(pf86, 'Python'));
  bases.push('C:\\');
  for (const base of bases) {
    try {
      for (const d of fs.readdirSync(base)) {
        if (base === 'C:\\' && !/^Python\d/i.test(d)) continue; // en C:\ solo carpetas Python3xx
        const p = path.join(base, d, 'python.exe');
        if (fs.existsSync(p)) cands.push(p);
      }
    } catch {}
  }
  for (const c of cands) if (fs.existsSync(c)) return c;
  return 'py'; // en instalaciones normales de python.org, 'py' es un ejecutable real y spawn lo corre
}
const PYTHON = buscarPython();
const POWERSHELL = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
console.log('Python:', PYTHON);

fs.mkdirSync(PDFS, { recursive: true });
fs.mkdirSync(path.join(AQUI, 'tmp_upload'), { recursive: true });

const app = express();
app.use(express.json({ limit: '2mb' }));
const upload = multer({ dest: path.join(AQUI, 'tmp_upload') });

const leerManifest = () => JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
const guardarManifest = (m) => { fs.writeFileSync(MANIFEST, JSON.stringify(m, null, 1)); marcarPendiente(); };
const marcarPendiente = () => fs.writeFileSync(PENDING, new Date().toISOString());
const hayPendiente = () => fs.existsSync(PENDING);

function safe(nombre) { return String(nombre).replace(/[^\w.\- ]/g, '_').trim(); }
function guardarPdf(tmpPath, nombreOrig) {
  const buf = fs.readFileSync(tmpPath);
  const h = crypto.createHash('sha256').update(buf).digest('hex').slice(0, 12);
  const dst = `${h}__${safe(nombreOrig)}`;
  fs.copyFileSync(tmpPath, path.join(PDFS, dst));
  fs.unlinkSync(tmpPath);
  return dst;
}

app.get('/api/certs', (req, res) => {
  res.json({ certs: leerManifest(), pendiente: hayPendiente(), base_url: CFG.base_url });
});

// cambiar estado (vigente|proceso|vencido) — NO cambia el id/QR
app.post('/api/status', (req, res) => {
  const { id, estado } = req.body;
  if (!['vigente', 'proceso', 'vencido'].includes(estado)) return res.status(400).json({ error: 'estado inválido' });
  const m = leerManifest();
  const it = m.find(x => x.id === id);
  if (!it) return res.status(404).json({ error: 'no encontrado' });
  it.estado = estado;
  guardarManifest(m);
  res.json({ ok: true });
});

// reemplazar el PDF de un certificado existente — conserva el id/QR
app.post('/api/replace', upload.single('pdf'), (req, res) => {
  const { id } = req.body;
  if (!req.file) return res.status(400).json({ error: 'falta el PDF' });
  const m = leerManifest();
  const it = m.find(x => x.id === id);
  if (!it) return res.status(404).json({ error: 'no encontrado' });
  it.pdf = guardarPdf(req.file.path, req.file.originalname);
  guardarManifest(m);
  res.json({ ok: true });
});

// agregar un certificado nuevo — genera un id/QR NUEVO (para imprimir)
app.post('/api/add', upload.single('pdf'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'falta el PDF' });
  const b = req.body;
  const m = leerManifest();
  m.push({
    id: '', hoja: b.hoja || 'MANUAL', fila: Number(b.fila) || (900 + m.length),
    clasif: b.clasif || '', disciplina: b.disciplina || '',
    codigo: b.codigo || '', nombre: b.nombre || 'Certificado', serial: b.serial || '',
    marca: b.marca || '', zona: b.zona || '',
    pdf: guardarPdf(req.file.path, req.file.originalname), estado: b.estado || 'vigente', paginas: 0, url: '',
  });
  guardarManifest(m);
  res.json({ ok: true });
});

// borrar el PDF de un certificado: el QR sigue vivo pero muestra solo el banner "en proceso"
app.post('/api/remove-pdf', (req, res) => {
  const m = leerManifest();
  const it = m.find(x => x.id === req.body.id);
  if (!it) return res.status(404).json({ error: 'no encontrado' });
  it.pdf = '';
  it.estado = 'proceso';
  it.paginas = 0;
  guardarManifest(m);
  res.json({ ok: true });
});

// editar datos de texto (nombre, codigo, serial, zona) — NO cambia el id/QR
app.post('/api/edit', (req, res) => {
  const { id, nombre, codigo, serial, zona } = req.body;
  const m = leerManifest();
  const it = m.find(x => x.id === id);
  if (!it) return res.status(404).json({ error: 'no encontrado' });
  if (nombre !== undefined) it.nombre = String(nombre).trim() || it.nombre;
  if (codigo !== undefined) it.codigo = String(codigo).trim();
  if (serial !== undefined) it.serial = String(serial).trim();
  if (zona !== undefined) it.zona = String(zona).trim();
  guardarManifest(m);
  res.json({ ok: true });
});

// eliminar el certificado por completo (si su QR ya se imprimió, mostraría "no encontrado")
app.post('/api/delete', (req, res) => {
  const m = leerManifest().filter(x => x.id !== req.body.id);
  guardarManifest(m);
  res.json({ ok: true });
});

app.get('/qr/:id.png', (req, res) => {
  const f = path.join(QRDIR, req.params.id + '.png');
  if (!fs.existsSync(f)) return res.status(404).end();
  res.sendFile(f);
});

// PUBLICAR: regenera el sitio y lo sube. Transmite el progreso en vivo.
let publicando = false;
app.get('/api/publish', (req, res) => {
  if (publicando) return res.status(409).end('Ya hay una publicación en curso.\n');
  publicando = true;
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  const log = (s) => { try { res.write(s); } catch {} };
  const correr = (cmd, args, cb) => {
    log(`\n$ ${cmd} ${args.join(' ')}\n`);
    let terminado = false;
    const fin = (code) => { if (!terminado) { terminado = true; cb(code); } };
    let p;
    try {
      p = spawn(cmd, args, { cwd: AQUI, windowsHide: true });
    } catch (e) {
      log(`\nNo se pudo iniciar: ${e.message}\n`);
      return fin(-1);
    }
    p.on('error', (err) => { log(`\nERROR al ejecutar (${cmd}): ${err.message}\n`); fin(-1); });
    p.stdout.on('data', d => log(d.toString()));
    p.stderr.on('data', d => log(d.toString()));
    p.on('close', code => fin(code));
  };
  log(`Regenerando el sitio (esto tarda 1-3 minutos)...\nUsando Python: ${PYTHON}\n`);
  correr(PYTHON, ['build_engine.py'], (c1) => {
    if (c1 !== 0) { publicando = false; log('\n❌ FALLÓ la regeneración del sitio.\n'); return res.end(); }
    correr(POWERSHELL, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'deploy.ps1'], (c2) => {
      publicando = false;
      if (c2 === 0) { try { fs.unlinkSync(PENDING); } catch {} log('\n✔ LISTO. Los cambios ya están en línea.\n'); }
      else log('\n❌ FALLÓ la publicación (revisa el token o la conexión).\n');
      res.end();
    });
  });
});

app.get('/', (req, res) => res.sendFile(path.join(AQUI, 'public', 'admin.html')));
app.use(express.static(path.join(AQUI, 'public')));

const servidor = app.listen(PORT, '127.0.0.1', () => {
  console.log(`Gestor de certificados en http://127.0.0.1:${PORT}`);
  // abrir el navegador SOLO cuando el servidor ya esta escuchando
  try { spawn('cmd', ['/c', 'start', '', `http://127.0.0.1:${PORT}`], { detached: true, stdio: 'ignore' }); } catch {}
});
servidor.on('error', (e) => {
  if (e.code === 'EADDRINUSE') {
    registrarError('El gestor YA ESTA ABIERTO en otra ventana (el puerto ' + PORT + ' esta ocupado).\n' +
      'Cierra la otra ventana negra del gestor y vuelve a intentarlo,\n' +
      'o simplemente abre en el navegador:  http://127.0.0.1:' + PORT);
  } else {
    registrarError('Error al abrir el servidor: ' + e.message);
  }
  process.exitCode = 1;
});
