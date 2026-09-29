const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const CLASES = {
  infanteria: { construye: false, carga_max: 0 },
  ingenieros: { construye: true, carga_max: 0 },
  transporte: { construye: false, carga_max: 100 },
  caza: { construye: false, carga_max: 0 },
  base_aerea: { construye: false, carga_max: 0 },
};
const clasePor = (u) => CLASES[u.clase] || null;
const u = (id, tipo, clase, extra = {}) => ({ id, bando: "azul", estado: "activa", tipo, clase, ...extra });
const UNIDADES = [
  u(1, "terrestre", "infanteria"), u(2, "terrestre", "ingenieros"), u(3, "terrestre", "transporte"),
  u(4, "aerea", "caza"), u(5, "base", "base_aerea"), u(6, "aerea", "caza", { estado: "destruida" }),
  u(7, "terrestre", "infanteria", { bando: "rojo" }),
];

test("la matriz de puestos coincide con la del servidor", () => {
  const f = (id) => L.puestoDe(id).funciones;
  assert.deepEqual(f("mando"), ["superficie", "aereo", "despegar", "logistica", "guerra_electronica", "listo"]);
  assert.deepEqual(f("inteligencia"), ["guerra_electronica"]);
  assert.deepEqual(f("operaciones"), ["aereo"]);
  assert.deepEqual(f("logistica"), ["logistica"]);
  assert.deepEqual(f("planificacion"), ["superficie", "despegar", "listo"]);
  assert.equal(L.puestoDe("").id, "mando");
  assert.equal(L.puestoDe(undefined).id, "mando");
  assert.equal(L.puestoDe("jefe").id, "mando");
  assert.equal(L.puestoPuede("planificacion", "listo"), true);
  assert.equal(L.puestoPuede("operaciones", "listo"), false);
});

test("funcionDeOrden clasifica igual que el servidor", () => {
  assert.equal(L.funcionDeOrden(u(1, "terrestre", "infanteria"), "mover", CLASES.infanteria), "superficie");
  assert.equal(L.funcionDeOrden(u(1, "terrestre", "infanteria"), "construir", CLASES.infanteria), "logistica");
  assert.equal(L.funcionDeOrden(u(2, "terrestre", "ingenieros"), "mover", CLASES.ingenieros), "logistica");
  assert.equal(L.funcionDeOrden(u(3, "terrestre", "transporte"), null, CLASES.transporte), "logistica");
  assert.equal(L.funcionDeOrden(u(4, "aerea", "caza"), "patrullar", CLASES.caza), "aereo");
  assert.equal(L.funcionDeOrden(u(5, "base", "base_aerea"), "despegar", CLASES.base_aerea), "despegar");
  assert.equal(L.funcionDeOrden(u(5, "base", "base_aerea"), null, null), "despegar");
  assert.equal(L.funcionDeOrden(u(1, "naval", "fragata"), "mover", null), "superficie");
});

test("unidadesDelPuesto deja a cada celula solo lo que conduce", () => {
  const ids = (puesto) => L.unidadesDelPuesto(UNIDADES, "azul", puesto, clasePor).map((x) => x.id);
  assert.deepEqual(ids("mando"), [1, 2, 3, 4]); // sin bases, sin destruidas, sin el enemigo
  assert.deepEqual(ids("inteligencia"), []);
  assert.deepEqual(ids("operaciones"), [4]);
  assert.deepEqual(ids("logistica"), [2, 3]);
  assert.deepEqual(ids("planificacion"), [1]);
});

test("etiquetas y aviso de unidad que conduce otro puesto", () => {
  assert.equal(L.etiquetaPuesto("operaciones"), "Operaciones en curso (A3)");
  assert.equal(L.etiquetaBando("azul", null, "planificacion"), "AZUL · PLANIFICACIÓN (A5)");
  assert.equal(L.etiquetaBando("azul", null), "AZUL (ALUMNO)"); // sin puesto: como antes
  assert.equal(L.etiquetaBando("instructor", "rojo"), "INSTRUCTOR · VISTA ROJO");
  assert.equal(L.textoPuestoAjeno(u(4, "aerea", "caza"), CLASES.caza), "Esta unidad la conduce el puesto Operaciones en curso (A3).");
  assert.equal(L.textoPuestoAjeno(u(2, "terrestre", "ingenieros"), CLASES.ingenieros), "Esta unidad la conduce el puesto Logística (A4).");
  assert.deepEqual(L.puestosResponsables("listo").map((p) => p.sigla), ["A5"]);
});
