const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const CLASES = {
  infanteria: { id: "infanteria", construye: false, carga_max: 0 },
  ingenieros: { id: "ingenieros", construye: true, carga_max: 0 },
  transporte: { id: "transporte", construye: false, carga_max: 100 },
  caza: { id: "caza", construye: false, carga_max: 0 },
  ataque: { id: "ataque", construye: false, carga_max: 0 },
  cisterna: { id: "cisterna", construye: false, carga_max: 100 },
  radar: { id: "radar", construye: false, carga_max: 0, emisor: true, solo_aereo: true, celula: "ge" },
  antiaerea: { id: "antiaerea", construye: false, carga_max: 0, defensa_aerea: true },
  reconocimiento: { id: "reconocimiento", construye: false, carga_max: 0 },
  base_aerea: { id: "base_aerea", construye: false, carga_max: 0 },
};
const clasePor = (u) => CLASES[u.clase] || null;
const u = (id, tipo, clase, extra = {}) => ({ id, bando: "azul", estado: "activa", tipo, clase, ...extra });
const UNIDADES = [
  u(1, "terrestre", "infanteria"), u(2, "terrestre", "ingenieros"), u(3, "terrestre", "transporte"),
  u(4, "aerea", "caza"), u(5, "base", "base_aerea"), u(6, "aerea", "caza", { estado: "destruida" }),
  u(7, "terrestre", "infanteria", { bando: "rojo" }), u(8, "terrestre", "radar"), u(9, "terrestre", "reconocimiento"),
  u(10, "aerea", "ataque"),
];

test("la matriz de reparticiones del TIEM coincide con la del servidor", () => {
  const f = (id) => L.puestoDe(id).funciones.slice().sort();
  const todas = ["aereo", "caza", "defensa_aerea", "despegar", "guerra_electronica", "listo", "logistica", "reconocimiento", "superficie"];
  assert.deepEqual(f("comandante"), todas);
  assert.deepEqual(f("jem"), todas);
  assert.deepEqual(f("a1"), []);
  assert.deepEqual(f("a2"), ["reconocimiento"]);
  assert.deepEqual(f("a3"), ["aereo", "caza", "despegar", "superficie"]);
  assert.deepEqual(f("a3da"), ["caza", "defensa_aerea", "despegar"]);
  assert.deepEqual(f("a4"), ["logistica"]);
  assert.deepEqual(f("ce"), ["guerra_electronica"]);
  assert.equal(L.puestoDe("").id, "comandante");
  assert.equal(L.puestoDe(undefined).id, "comandante");
  assert.equal(L.puestoDe("jefe").id, "comandante");
  assert.equal(L.puestoPuede("jem", "listo"), true);
  assert.equal(L.puestoPuede("a3", "listo"), false);
});

test("los puestos anteriores al TIEM se traducen", () => {
  const ids = ["mando", "inteligencia", "operaciones", "logistica", "planificacion"].map((p) => L.puestoDe(p).id);
  assert.deepEqual(ids, ["comandante", "a2", "a3", "a4", "a3"]);
});

test("funcionDeOrden clasifica igual que el servidor", () => {
  assert.equal(L.funcionDeOrden(u(1, "terrestre", "infanteria"), "mover", CLASES.infanteria), "superficie");
  assert.equal(L.funcionDeOrden(u(1, "terrestre", "infanteria"), "construir", CLASES.infanteria), "logistica");
  assert.equal(L.funcionDeOrden(u(2, "terrestre", "ingenieros"), "mover", CLASES.ingenieros), "logistica");
  assert.equal(L.funcionDeOrden(u(3, "terrestre", "transporte"), null, CLASES.transporte), "logistica");
  assert.equal(L.funcionDeOrden(u(4, "aerea", "caza"), "patrullar", CLASES.caza), "caza");
  assert.equal(L.funcionDeOrden(u(10, "aerea", "ataque"), "atacar", CLASES.ataque), "aereo");
  assert.equal(L.funcionDeOrden(u(11, "aerea", "cisterna"), "mover", CLASES.cisterna), "aereo"); // el cisterna no es un convoy
  assert.equal(L.funcionDeOrden(u(8, "terrestre", "radar"), "mover", CLASES.radar), "defensa_aerea");
  assert.equal(L.funcionDeOrden(u(12, "terrestre", "antiaerea"), "mover", CLASES.antiaerea), "defensa_aerea");
  assert.equal(L.funcionDeOrden(u(13, "aerea", "alerta_temprana"), "mover", null), "defensa_aerea");
  assert.equal(L.funcionDeOrden(u(9, "terrestre", "reconocimiento"), "mover", CLASES.reconocimiento), "reconocimiento");
  assert.equal(L.funcionDeOrden(u(14, "aerea", "dron_reconocimiento"), "mover", null), "reconocimiento");
  assert.equal(L.funcionDeOrden(u(5, "base", "base_aerea"), "despegar", CLASES.base_aerea), "despegar");
  assert.equal(L.funcionDeOrden(u(5, "base", "base_aerea"), null, null), "despegar");
  assert.equal(L.funcionDeOrden(u(1, "naval", "fragata"), "mover", null), "superficie");
});

test("unidadesDelPuesto deja a cada reparticion solo lo que conduce", () => {
  const ids = (puesto) => L.unidadesDelPuesto(UNIDADES, "azul", puesto, clasePor).map((x) => x.id);
  assert.deepEqual(ids("comandante"), [1, 2, 3, 4, 8, 9, 10]); // sin bases, sin destruidas, sin el enemigo
  assert.deepEqual(ids("a1"), []);
  assert.deepEqual(ids("a2"), [9]);
  assert.deepEqual(ids("a3"), [1, 4, 10]);
  assert.deepEqual(ids("a3da"), [4, 8]);
  assert.deepEqual(ids("a4"), [2, 3]);
  assert.equal(L.puestoPuedeAereo("a3da"), true);
  assert.equal(L.puestoPuedeAereo("a4"), false);
});

test("etiquetas y aviso de unidad que conduce otra reparticion", () => {
  assert.equal(L.etiquetaPuesto("a3da"), "Defensa Aérea (A-3 D/A)");
  assert.equal(L.etiquetaBando("azul", null, "a3"), "AZUL · OPERACIONES (A-3)");
  assert.equal(L.etiquetaBando("azul", null), "AZUL (ALUMNO)"); // sin puesto: como antes
  assert.equal(L.etiquetaBando("instructor", "rojo"), "INSTRUCTOR · VISTA ROJO");
  assert.equal(L.textoPuestoAjeno(u(4, "aerea", "caza"), CLASES.caza), "Esta unidad la conduce la repartición Operaciones (A-3) o Defensa Aérea (A-3 D/A).");
  assert.equal(L.textoPuestoAjeno(u(2, "terrestre", "ingenieros"), CLASES.ingenieros), "Esta unidad la conduce la repartición Logística (A-4).");
  assert.deepEqual(L.puestosResponsables("listo"), []);
});
