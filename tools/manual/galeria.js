/* Genera tools/manual/salida/galeria.html: galeria de miniaturas 3D (HTML estatico) para capturarla con Chrome. */
const fs = require("fs"), path = require("path");
const M = require("../../frontend/static/js/modelo3d.js"); require("../../frontend/static/js/miniaturas.js");
const out = path.join(__dirname, "salida"); fs.mkdirSync(out, { recursive: true });
const N = {
  f16: ["F-16", "imagen de modelo 3D real"], su30: ["Su-30", "imagen de modelo 3D real"], generico: ["Caza genérico", "enemigo no identificado"],
  caza_embarcado: ["Caza embarcado", "opera desde portaaviones"], ataque_ligero: ["Avión de ataque ligero", ""], helo_ataque: ["Helicóptero de ataque", ""],
  helo_transporte: ["Helicóptero de transporte", "artillado"], dron_reconocimiento: ["Dron de reconocimiento", ""], dron_armado: ["Dron armado", ""],
  merodeadora: ["Munición merodeadora", "dron kamikaze"], avion_ge: ["Avión de guerra electrónica", ""], misil_crucero: ["Misil de crucero", "salva"],
  infanteria: ["Infantería", ""], antiaerea_portatil: ["Antiaérea portátil", "tipo IGLA-S"], tanque: ["Blindados", ""], artilleria: ["Artillería", "autopropulsada"],
  reconocimiento: ["Reconocimiento", "blindado 8x8"], antiaerea: ["Defensa antiaérea", "guiada por radar"], ingenieros: ["Ingenieros", "puentes y vados"],
  convoy: ["Transporte logístico", "convoy"], radar: ["Radar de vigilancia", ""], guerra_electronica: ["Guerra electrónica", "escucha e interferencia"],
  lanzador_misiles: ["Lanzador de misiles", "batería costera"], patrullero: ["Patrullero", ""], fragata: ["Fragata", ""], destructor: ["Destructor", ""],
  portaaviones: ["Portaaviones", ""], submarino: ["Submarino", ""], buque_desembarco: ["Buque de desembarco", ""], base_aerea: ["Base aérea", ""],
  deposito: ["Depósito logístico", ""], puerto: ["Puerto / base naval", ""],
};
let cards = "";
for (const id of M.MALLAS) {
  const info = M.info(id), px = Math.round(100 * (info.tam || 1)), rumbo = info.rumbo ?? 40;
  const html = M.tieneSprite(id)
    ? `<img src="http://127.0.0.1:8000${M.urlSprite(id, 45)}" width="100" height="100"><img src="http://127.0.0.1:8000${M.urlSprite(id, 135)}" width="100" height="100">`
    : M.svg({ modelo: id, rumbo, bando: "azul", px }) + M.svg({ modelo: id, rumbo: (rumbo + 90) % 360, bando: "rojo", px });
  const [n, s] = N[id] || [id, ""];
  cards += `<div class="t"><div class="f">${html}</div><b>${n}</b><small>${s || "&nbsp;"}</small></div>`;
}
fs.writeFileSync(path.join(out, "galeria.html"), `<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
body{margin:0;padding:14px 18px;background:#fff;font:13px 'Segoe UI',Arial,sans-serif;color:#1c2530}
.rejilla{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px 10px}
.t{text-align:center;background:#f4f6f9;border:1px solid #d5dbe2;border-radius:8px;padding:6px 4px 4px}
.t .f{display:flex;justify-content:center;align-items:center;gap:4px;height:118px}.t b{display:block;font-size:12.5px}.t small{color:#5a6774;font-size:11px}
svg{filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}.t svg,.t img{max-width:48%;height:auto}</style></head><body><div class="rejilla">${cards}</div></body></html>`, "utf8");
console.log("galeria.html", M.MALLAS.length, "miniaturas");
