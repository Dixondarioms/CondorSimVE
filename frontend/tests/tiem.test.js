const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");
globalThis.Logica = L;
const P = require("../static/js/pmo.js");

test("la misión se arma como TAREA ... a fin de PROPÓSITO, igual que el servidor", () => {
  const m = { tarea: "Conducir operaciones aéreas defensivas", que: "para impedir la superioridad aérea enemiga", donde: "en el área de operaciones", cuando: "a partir de D/H", proposito: "preservar la soberanía" };
  assert.equal(P.textoMision(m), "Conducir operaciones aéreas defensivas para impedir la superioridad aérea enemiga en el área de operaciones a partir de D/H, a fin de preservar la soberanía.");
  assert.deepEqual(P.avisosMision(m), []);
  const mal = P.avisosMision({ ...m, tarea: "Operaciones defensivas", proposito: "", cuando: "si el enemigo ataca" }).join(" ");
  assert.match(mal, /infinitivo/);
  assert.match(mal, /propósito/);
  assert.match(mal, /condiciones/);
  assert.equal(P.textoMision({}), "");
});

test("bloques: las líneas con «- » son viñetas", () => {
  assert.deepEqual(P.bloques("Intro\n- uno\n- dos\n\nFin"), [
    { tipo: "p", texto: "Intro" }, { tipo: "li", texto: "uno" }, { tipo: "li", texto: "dos" }, { tipo: "p", texto: "Fin" }]);
});

test("fases del calendario con referencias a H y la fase en curso", () => {
  const cal = { turno_h: 3, fases: [{ nombre: "Concentracion y despliegue", desde: 1, hasta: 2 }, { nombre: "Ejecucion", desde: 3, hasta: null }] };
  assert.deepEqual(P.filasFases(cal, 4), [
    { nombre: "Concentración y despliegue", rango: "turnos 1–2 (H-2 a H-1)", actual: false },
    { nombre: "Ejecución", rango: "turnos 3–… (H en adelante)", actual: true },
  ]);
  assert.equal(L.textoCalendario({ actual: { dia: "D+1", hora_h: "H+20", fase: "Ejecucion" } }), "D+1 · H+20 · Ejecución");
  assert.equal(L.textoCalendario(null), "");
});

test("la cadena de objetivos se muestra como árbol", () => {
  const objs = [
    { id: 5, nivel: "material", padre_id: 2, tipo: "destruir" },
    { id: 2, nivel: "asignado", padre_id: 1, tipo: "efecto" },
    { id: 9, nivel: "material", padre_id: null, tipo: "ocupar" },
    { id: 1, nivel: "ulterior", padre_id: null, tipo: "efecto" },
    { id: 7, nivel: "material", padre_id: 2, tipo: "proteger" },
  ];
  assert.deepEqual(L.arbolObjetivos(objs).map(({ o, nivel }) => [o.id, nivel]), [[1, 0], [2, 1], [5, 2], [7, 2], [9, 0]]);
  // un superior que el bando no ve deja al objetivo como raiz
  assert.deepEqual(L.arbolObjetivos([{ id: 5, padre_id: 99, nivel: "material" }]).map(({ o }) => o.id), [5]);
  assert.deepEqual(L.superioresPosibles(objs.map((o) => ({ ...o, bando: "azul" })), "azul", "material").map((o) => o.id), [2, 1]);
  assert.deepEqual(L.superioresPosibles(objs.map((o) => ({ ...o, bando: "azul" })), "azul", "asignado").map((o) => o.id), [1]);
});

test("textos de los objetivos nuevos: neutralizar, efecto y plazo", () => {
  assert.equal(L.textoObjetivo({ tipo: "neutralizar", unidad_nombre: "SAM", umbral: 40, puntos: 15, hasta_turno: 8 }), "Neutralizar SAM (fuerza 40 % o menos) · plazo: turno 8 · 15 pts");
  assert.equal(L.textoObjetivo({ tipo: "efecto", nivel: "asignado", umbral: 75, puntos: 0 }), "Cumplir el 75 % de los objetivos que dependen de él");
  assert.deepEqual(L.avanceObjetivo({ tipo: "efecto", estado: "pendiente", avance: { cumplidos: 1, total: 3, requerido_pct: 75 } }), { texto: "1/3 cumplidos", clase: "mov" });
  assert.equal(L.textoObjetivo({ tipo: "proteger", unidad_nombre: "BA", hasta_turno: 6, puntos: 20 }), "Proteger BA hasta el turno 6 · 20 pts");
});
