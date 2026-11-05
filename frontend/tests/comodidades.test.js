const test = require("node:test");
const assert = require("node:assert/strict");
const I = require("../static/js/interfaz.js");

test("cada alerta cae en su filtro", () => {
  assert.equal(I.grupoAlerta({ causa: "ataque" }), "ataques");
  assert.equal(I.grupoAlerta({ causa: "contacto" }), "contactos");
  assert.equal(I.grupoAlerta({ causa: "evento" }), "director");
  assert.equal(I.grupoAlerta({}), "otras");
  assert.ok(I.pasaFiltro({ causa: "zona" }, "contactos") && !I.pasaFiltro({ causa: "zona" }, "ataques"));
  assert.ok(I.pasaFiltro({ causa: "zona" }, "todas") && I.pasaFiltro({}, undefined));
});

test("los atajos no se disparan al escribir ni con una ventana abierta, y el reloj es del director", () => {
  const tecla = (key, tag = "DIV", extra = {}) => ({ key, target: { tagName: tag }, ...extra });
  assert.equal(I.accionDeTecla(tecla("m"), false, false), "mover");
  assert.equal(I.accionDeTecla(tecla("I"), false, false), "interceptar");
  assert.equal(I.accionDeTecla(tecla("m", "INPUT"), false, false), null);
  assert.equal(I.accionDeTecla(tecla("m"), false, true), null);
  assert.equal(I.accionDeTecla(tecla("m", "DIV", { ctrlKey: true }), false, false), null);
  assert.equal(I.accionDeTecla(tecla(" "), false, false), null);
  assert.equal(I.accionDeTecla(tecla(" "), true, false), "marcha");
  assert.equal(I.accionDeTecla(tecla("3"), true, false), "vel-60");
  assert.ok(I.ATAJOS.length >= 8 && I.FILTROS[0][0] === "todas");
});

test("las señales del icono muestran lo urgente de una unidad propia y nada del enemigo", () => {
  const L = require("../static/js/logica.js");
  const propia = { estado: "activa", tipo: "aerea", combustible: 20, municion: 0, enlace: false,
    apresto: { minutos: 15, despega_en_min: 7 }, sistemas: { radar: { nombre: "Radar", fuera: true } } };
  assert.deepEqual(L.senalesUnidad(propia).map((s) => s.clase), ["despega", "combustible", "municion", "enlace", "averia"]);
  assert.deepEqual(L.senalesUnidad({ estado: "activa", tipo: "terrestre", combustible: 80, municion: 60 }), []);
  assert.deepEqual(L.senalesUnidad({ estado: "activa", tipo: "terrestre", combustible: null, municion: null }), []);  // enemiga
});

test("la ruta estima cuando llega y con cuanto combustible a cada punto, con la velocidad de cada tramo", () => {
  const L = require("../static/js/logica.js");
  const caza = { tipo: "aerea", lat: 0, lon: 0, velocidad_kmh: 900, autonomia_km: 1800, combustible: 100 };
  const pts = [[0, 1], [0, 2]];  // unos 111 km cada tramo
  const [a, b] = L.estimarRuta(caza, pts, []);
  assert.ok(Math.abs(a.minutos - 7) <= 1 && Math.abs(b.minutos - 15) <= 1);
  assert.ok(Math.abs(a.combustible - 94) <= 1);
  const [, rapido] = L.estimarRuta(caza, pts, [{}, { velocidad: "maxima" }]);
  assert.ok(rapido.minutos < b.minutos && rapido.combustible < b.combustible);
  assert.match(L.textoPuntoRuta(1, b), /^W2 · en \d+ min · combustible \d+ %/);
  assert.deepEqual(L.estimarRuta({ ...caza, velocidad_kmh: 0 }, pts), []);
});

test("de los nombres que se pisan se ve uno solo, el de la unidad elegida si esta", () => {
  const L = require("../static/js/logica.js");
  const tapados = L.rotulosTapados([{ id: 1, x: 100, y: 100 }, { id: 2, x: 110, y: 105, prioridad: 2 }, { id: 3, x: 400, y: 100 }]);
  assert.deepEqual([...tapados], [1]);
});

test("los anillos de alcance de cada arma: antiaerea, carga, torpedo, defensa de punto y balistico", () => {
  const L = require("../static/js/logica.js");
  const cat = {
    sistemas_da: { s300vm: { armas: [{ nombre: "9M83", alcance_max_km: 75 }, { nombre: "9M82", alcance_max_km: 200 }] } },
    armas: { M120: { nombre: "AIM-120", alcance_km: 70 }, M9X: { nombre: "AIM-9X", alcance_km: 18 } },
    asw: { aviones: [], helos: [], torpedo_km: { fragata: 10 } }, defensa_punto: { fragata: { canales: 2, km: 8, pk: 0.45 } },
  };
  assert.deepEqual(L.anillosArmas({ estado: "activa", modelo: "s300vm" }, cat).map((a) => a.km), [200, 75]);
  assert.deepEqual(L.anillosArmas({ estado: "activa", tipo: "aerea", armamento: { quedan: { M120: 4, M9X: 0 } } }, cat).map((a) => a.nombre), ["AIM-120"]);
  assert.deepEqual(L.anillosArmas({ estado: "activa", tipo: "naval", clase: "fragata" }, cat).map((a) => a.nombre), ["Torpedo", "Defensa de punto"]);
  assert.equal(L.anillosArmas({ estado: "activa", clase: "lanzador_balistico" }, cat)[0].km, 500);
});

test("de lejos las aeronaves se achican mas y el grupo muestra menos siluetas", () => {
  const L = require("../static/js/logica.js");
  for (const z of [10, 11, 14]) assert.equal(L.escalaAeronave(z), L.escalaUnidad(z));  // de cerca, igual que antes
  assert.ok(L.escalaAeronave(8) < L.escalaUnidad(8) && L.escalaAeronave(7) < L.escalaAeronave(8));
  assert.equal(L.escalaAeronave(3), 0.28);
  assert.equal(L.siluetasGrupo(4, 9), 4);
  assert.equal(L.siluetasGrupo(4, 8), 2);
  assert.equal(L.siluetasGrupo(4, 6), 1);
  assert.equal(L.siluetasGrupo(undefined, 6), 1);
});
