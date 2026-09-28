const test = require("node:test");
const assert = require("node:assert/strict");
const { layout } = require("../static/js/timeline.js");

const serie = (id, nombre, bando, comb, mun, estado) => ({
  unidad_id: id, nombre, bando, clase: "infanteria", turnos: comb.map((_, i) => i),
  combustible: comb, municion: mun, fuerza: comb.map(() => 100), estado: estado || comb.map(() => "activa"),
});

function datos() {
  return {
    ejes: { turnos: [0, 1, 2, 3], hora_inicio_min: 360, umbrales: { caida_abrupta: 30, nivel_critico: 25 } },
    series: [
      serie(2, "R1", "rojo", [100, 100, 90, 90], [100, 100, 100, 60], ["activa", "activa", "activa", "destruida"]),
      serie(3, "B", "azul", [100, 100, 100, 100], [100, 100, 100, 100]),
      serie(1, "A", "azul", [100, 60, 60, 20], [100, 75, 15, 15]),
    ],
    eventos: [
      { id: "e1", tipo: "evento", subtipo: "clima", turno: 1, texto: "lluvia", bando_destino: "todos" },
      { id: "e2", tipo: "evento", subtipo: "ajuste", turno: 1, texto: "ajuste", bando_destino: "instructor" },
      { id: "c1", tipo: "combate", subtipo: "ataque", turno: 1, atacante_id: 1, defensor_id: 2, atacante: "A", defensor: "R1", ratio: 1.2, perdida_atacante: 10, perdida_defensor: 20, terreno: "llano", efectos: [], lat: 8, lon: -70, orden_id: 5 },
      { id: "c2", tipo: "combate", subtipo: "ataque", turno: 2, atacante_id: 1, defensor_id: 2, atacante: "A", defensor: "R1", ratio: 1.1, perdida_atacante: 12, perdida_defensor: 18, terreno: "llano", efectos: [], lat: 8, lon: -70, orden_id: 6 },
      { id: "l1-1-municion", tipo: "logistico", subtipo: "nivel_critico", turno: 2, unidad_id: 1, unidad: "A", bando: "azul", variable: "municion", antes: 75, despues: 15, delta: -60, causas: ["combate"], orden_ids: [6] },
      { id: "l1-1-combustible", tipo: "logistico", subtipo: "caida_abrupta", turno: 1, unidad_id: 1, unidad: "A", bando: "azul", variable: "combustible", antes: 100, despues: 60, delta: -40, causas: ["movimiento"], orden_ids: [4] },
    ],
    correlaciones: [
      { tipo: "consumo_en_combate", turno: 2, unidad_id: 1, logistico: "l1-1-municion", combate: "c2", detalle: "municion 75% -> 15%" },
      { tipo: "coincide_con_combate", turno: 1, unidad_id: 1, logistico: "l1-1-combustible", combate: "c1", detalle: "combustible 100% -> 60% (movimiento)" },
      { tipo: "combate_con_logistica_baja", turno: 3, unidad_id: 1, logistico: null, combate: "c3", detalle: "atacante con municion 15%" },
    ],
    resumen: {},
  };
}

const OP = { ancho: 1000, margenIzq: 100, margenDer: 20, margenSup: 40, altoCarril: 30 };

test("sin turnos el diagrama esta vacio", () => {
  const L = layout({ ejes: { turnos: [] }, series: [], eventos: [], correlaciones: [] });
  assert.equal(L.vacio, true);
  assert.deepEqual([L.carriles, L.marcas, L.enlaces], [[], [], []]);
});

test("los turnos se reparten proporcionalmente entre los margenes", () => {
  const L = layout(datos(), OP);
  assert.deepEqual(L.ticks.map((t) => t.turno), [0, 1, 2, 3]);
  assert.equal(L.ticks[0].x, 100);
  assert.equal(L.ticks[3].x, 980);
  assert.ok(Math.abs(L.ticks[1].x - (100 + 880 / 3)) < 1e-9);
});

test("un unico turno no divide por cero", () => {
  const d = datos();
  d.ejes.turnos = [0];
  d.series = [serie(1, "A", "azul", [100], [100])];
  d.eventos = []; d.correlaciones = [];
  const L = layout(d, OP);
  assert.equal(L.ticks[0].x, 100);
  assert.equal(L.carriles[0].combustible[0][0], 100);
});

test("los carriles van primero azul y despues rojo, por nombre", () => {
  const L = layout(datos(), OP);
  assert.deepEqual(L.carriles.map((c) => c.nombre), ["A", "B", "R1"]);
  assert.deepEqual(L.carriles.map((c) => c.y), [40, 70, 100]);
  assert.equal(L.alto, 40 + 3 * 30 + 18);
});

test("las series se dibujan de 0 % (abajo) a 100 % (arriba) dentro de su carril", () => {
  const A = layout(datos(), OP).carriles[0];
  const [y100] = [A.combustible[0][1]];
  const y60 = A.combustible[1][1];
  const y20 = A.combustible[3][1];
  assert.equal(y100, 40 + 30 - 4 - 22); // tope: 100 %
  assert.ok(y60 > y100 && y20 > y60); // baja el combustible -> baja la linea
  const R = layout(datos(), OP).carriles[2];
  assert.equal(R.destruida, 100 + (880 * 3) / 3); // marca donde la unidad se destruye (turno 3)
  assert.equal(A.destruida, null);
});

test("cada combate marca a atacante y defensor, y solo a los que tienen carril", () => {
  const L = layout(datos(), OP);
  const c1 = L.marcas.filter((m) => m.id === "c1");
  assert.deepEqual(c1.map((m) => [m.unidad_id, m.subtipo]).sort(), [[1, "atacante"], [2, "defensor"]]);
  assert.equal(c1[0].x, L.ticks[1].x);
  const soloAzul = layout(datos(), { ...OP, bando: "azul" });
  assert.deepEqual(soloAzul.marcas.filter((m) => m.id === "c1").map((m) => m.unidad_id), [1]);
  assert.deepEqual(soloAzul.carriles.map((c) => c.nombre), ["A", "B"]);
});

test("los eventos logisticos se ubican en la unidad, separados por variable", () => {
  const L = layout(datos(), OP);
  const mun = L.marcas.find((m) => m.id === "l1-1-municion");
  const com = L.marcas.find((m) => m.id === "l1-1-combustible");
  assert.equal(mun.y, L.carriles[0].yCentro);
  assert.equal(mun.x, L.ticks[2].x - 5);
  assert.equal(com.x, L.ticks[1].x + 5);
  assert.equal(mun.subtipo, "nivel_critico");
});

test("los eventos van sobre el eje y se apilan cuando coinciden en el turno", () => {
  const L = layout(datos(), OP);
  const ev = L.marcas.filter((m) => m.tipo === "evento");
  assert.equal(ev.length, 2);
  assert.ok(ev.every((m) => m.y === 40 - 16));
  assert.equal(ev[1].x - ev[0].x, 9);
});

test("los eventos dirigidos a un bando se filtran, y el instructor ve los suyos solo en la vista completa", () => {
  const d = datos();
  d.eventos.push({ id: "e3", tipo: "evento", subtipo: "general", turno: 2, texto: "solo rojo", bando_destino: "rojo" });
  assert.equal(layout(d, { ...OP, bando: "azul" }).marcas.filter((m) => m.tipo === "evento").length, 1);
  assert.equal(layout(d, { ...OP, bando: "rojo" }).marcas.filter((m) => m.tipo === "evento").length, 2);
  assert.equal(layout(d, OP).marcas.filter((m) => m.tipo === "evento").length, 3);
});

test("los enlaces unen el gasto logistico con su combate", () => {
  const L = layout(datos(), OP);
  const consumo = L.enlaces.find((e) => e.tipo === "consumo_en_combate");
  assert.equal(consumo.de, "l1-1-municion@1");
  assert.equal(consumo.a, "c2@1");
  const mun = L.marcas.find((m) => m.id === "l1-1-municion");
  const c2 = L.marcas.find((m) => m.clave === "c2@1");
  assert.ok(consumo.ruta.startsWith(`M${mun.x.toFixed(1)} ${mun.y.toFixed(1)}`));
  assert.ok(consumo.ruta.endsWith(`${c2.x.toFixed(1)} ${c2.y.toFixed(1)}`));
  assert.equal(L.enlaces.filter((e) => e.tipo === "coincide_con_combate").length, 1);
});

test("un enlace sin evento logistico parte del estado del turno anterior", () => {
  const d = datos();
  d.eventos.push({ id: "c3", tipo: "combate", subtipo: "ataque", turno: 3, atacante_id: 1, defensor_id: 2, atacante: "A", defensor: "R1", ratio: 1, perdida_atacante: 1, perdida_defensor: 1, terreno: "llano", efectos: [], lat: 0, lon: 0, orden_id: 7 });
  const L = layout(d, OP);
  const baja = L.enlaces.find((e) => e.tipo === "combate_con_logistica_baja");
  assert.equal(baja.de, null);
  assert.ok(baja.ruta.startsWith(`M${L.ticks[2].x.toFixed(1)} `));
});

test("los enlaces desaparecen si el filtro oculta alguno de sus extremos", () => {
  assert.equal(layout(datos(), { ...OP, mostrar: { combates: false } }).enlaces.length, 0);
  assert.equal(layout(datos(), { ...OP, mostrar: { logistica: false } }).enlaces.filter((e) => e.de).length, 0);
  const sinEventos = layout(datos(), { ...OP, mostrar: { eventos: false } });
  assert.equal(sinEventos.marcas.filter((m) => m.tipo === "evento").length, 0);
  assert.ok(sinEventos.enlaces.length >= 2);
});

test("un enlace hacia un combate cuyo carril no se muestra se omite", () => {
  const L = layout(datos(), { ...OP, bando: "rojo" });
  assert.equal(L.enlaces.length, 0); // A (azul) no tiene carril
});
