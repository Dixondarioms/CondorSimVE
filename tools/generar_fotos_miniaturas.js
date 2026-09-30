/* Genera las "fotos" (ilustraciones SVG de 640x360) de los modelos genericos del catalogo a partir de sus
 * miniaturas 3D (frontend/static/js/miniaturas.js): mismo estilo que las ilustraciones propias de los drones,
 * cedidas al dominio publico (CC0). Se corre con Node desde la raiz del proyecto:
 *
 *     node tools/generar_fotos_miniaturas.js
 *
 * Escribe frontend/static/fotos/<modelo>.svg para cada entrada de MODELOS de abajo. */
const fs = require("node:fs");
const path = require("node:path");

const M = require("../frontend/static/js/modelo3d.js");
require("../frontend/static/js/miniaturas.js");

// modelo del catalogo -> { malla, nombre, rumbo (grados), fondo ("cielo" | "mar"), escala }
const MODELOS = {
  caza_embarcado: { malla: "caza_embarcado", nombre: "Caza embarcado (genérico)", rumbo: 215, fondo: "cielo" },
  helo_ataque: { malla: "helo_ataque", nombre: "Helicóptero de ataque (genérico)", rumbo: 230, fondo: "cielo" },
  helo_transporte: { malla: "helo_transporte", nombre: "Helicóptero de transporte artillado (genérico)", rumbo: 225, fondo: "cielo" },
  ataque_ligero: { malla: "ataque_ligero", nombre: "Avión de ataque ligero (genérico)", rumbo: 220, fondo: "cielo" },
  crucero: { malla: "misil_crucero", nombre: "Misil de crucero (genérico)", rumbo: 250, fondo: "mar", escala: 0.9 },
};

const FONDOS = {
  cielo: { arriba: "#1d2433", abajo: "#4a5568", suelo: "#3b4a3a" },
  mar: { arriba: "#1c2a3d", abajo: "#2f5f86", suelo: "#1f3f5c" },
};

function ilustracion(id, cfg) {
  const f = FONDOS[cfg.fondo];
  const lado = Math.round(400 * (cfg.escala || 1));
  const cuerpo = M.svg({ modelo: cfg.malla, rumbo: cfg.rumbo, bando: "neutro", px: lado })
    .replace(/^<svg [^>]*>/, "").replace(/<\/svg>$/, "");
  const h = M.semilado(cfg.malla, 1);
  const k = lado / (2 * h); // unidades de la malla -> pixeles
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-label="${cfg.nombre} (ilustración)">
  <defs>
    <linearGradient id="fondo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${f.arriba}"/><stop offset="1" stop-color="${f.abajo}"/></linearGradient>
    <radialGradient id="brillo" cx=".5" cy=".35" r=".6"><stop offset="0" stop-color="#ffffff" stop-opacity=".16"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="640" height="360" fill="url(#fondo)"/>
  <rect width="640" height="360" fill="url(#brillo)"/>
  <rect y="300" width="640" height="60" fill="${f.suelo}" opacity=".55"/>
  <g transform="translate(320 190) scale(${k.toFixed(4)})">${cuerpo}</g>
  <text x="620" y="346" fill="#c9d3dc" font-family="system-ui, sans-serif" font-size="13" text-anchor="end" opacity=".8">Ilustración propia · miniatura 3D del simulador · CC0</text>
</svg>
`;
}

const destino = path.join(__dirname, "..", "frontend", "static", "fotos");
for (const [id, cfg] of Object.entries(MODELOS)) {
  fs.writeFileSync(path.join(destino, `${id}.svg`), ilustracion(id, cfg), "utf8");
  console.log(`${id}.svg`);
}
