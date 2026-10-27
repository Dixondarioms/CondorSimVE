const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("../static/js/situacion.js");

test("duracion en horas y minutos, y en dias para recorridos largos", () => {
  assert.equal(S.duracion(0.75), "45 min");
  assert.equal(S.duracion(3.3334), "3 h 20 min");
  assert.equal(S.duracion(2), "2 h");
  assert.equal(S.duracion(26.5), "1 día 2 h");
  assert.equal(S.duracion(0), "0 min");
});

test("tiempo de todo el recorrido de una orden de mover, con llegada y avisos", () => {
  const t = S.textoTiempo({ km: 87, horas: 3.33, turnos: 4, llegada: "14:20", llegada_dias: 0, bloqueo: "", km_combustible: 300 });
  assert.equal(t, "Recorrido completo: 87 km en 3 h 20 min; llegada estimada 14:20h.");
  assert.match(S.textoTiempo({ km: 500, horas: 20, turnos: 20, llegada: "02:00", llegada_dias: 1, km_combustible: 300 }),
    /\(\+1 día\)\. El combustible alcanza para 300 km/);
  assert.match(S.textoTiempo({ km: 12, horas: 0.5, turnos: 1, bloqueo: "Río sin puente ni vado en la ruta." }), /Río sin puente/);
  assert.equal(S.textoTiempo({ km: 0 }), "");
});

test("porcentaje de objetivos cumplidos", () => {
  assert.equal(S.textoObjetivos({ asignados: 5, cumplidos: 2, cumplidos_pct: 40 }), "2 de 5 cumplidos (40 %)");
  assert.equal(S.textoObjetivos({ asignados: 0 }), "sin objetivos");
});

test("cuadro radar: lineas de contacto, estado del sensor y mensaje para la red del bando", () => {
  const c = { unidad_id: 9, nombre: "Caza R", clase: "caza", distancia_km: 84.6, rumbo: 40, en_vuelo: true, perfil: "medio" };
  assert.equal(S.lineaContacto(c), "Caza R · 85 km · rumbo 040° · cota media");
  assert.equal(S.estadoSensor({ emisor: true, emitiendo: true, interferido: true, energia_pct: 70 }), "emitiendo · interferido · energía de respaldo: 70 % del alcance");
  assert.equal(S.estadoSensor({ emisor: false, emitiendo: true }), "escucha pasiva (no emite)");
  const sensores = [
    { nombre: "Radar Norte", contactos: [c] },
    { nombre: "AA Pesada", contactos: [c, { unidad_id: 10, nombre: "Helo R", clase: "helicoptero", distancia_km: 12, rumbo: 300, en_vuelo: true, perfil: "rasante" }] },
    { nombre: "Radar Sur", contactos: [] },
  ];
  const m = S.mensajeRadar(sensores, 4, "09:00");
  assert.match(m, /^Cuadro radar turno 4 \(09:00\), 2 contacto\(s\)\./);
  assert.match(m, /AA Pesada: Helo R · 12 km · rumbo 300° · rasante/);
  assert.ok(!m.includes("Radar Sur"));
  assert.equal(S.mensajeRadar([{ nombre: "R", contactos: [] }], 1, "06:00"), "Cuadro radar turno 1 (06:00): sin contactos enemigos.");
  const muchos = Array.from({ length: 40 }, (_, i) => ({ ...c, unidad_id: i, nombre: `Contacto número ${i}` }));
  assert.ok(S.mensajeRadar([{ nombre: "R", contactos: muchos }], 1, "06:00").length <= 500);
});

const L = require("../static/js/logica.js");
const I = require("../static/js/infraestructura.js");

test("estado de la infraestructura: operativa, dañada o puente cortado, y su rama propia", () => {
  const puente = { clase: "puente", tipo: "base", estado: "activa", fuerza: 30 };
  assert.deepEqual(L.estadoUnidad(puente), { texto: "Cortado", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad({ ...puente, clase: "refineria", fuerza: 60 }), { texto: "Dañada (60 %)", clase: "mov" });
  assert.deepEqual(L.estadoUnidad({ ...puente, fuerza: 100 }), { texto: "Operativa", clase: "ok" });
  assert.equal(L.ramaDe({ clase: "termoelectrica", tipo: "base" }), "infraestructura");
});

test("capa de infraestructura: ficha y si ya esta en el ejercicio", () => {
  const p = { nombre: "Puente Angostura", clase: "puente", lat: 8.144, lon: -63.598, largo_km: 1.16, radio_km: 0.9 };
  assert.deepEqual(I.filasFicha(p).map((f) => f[0]), ["Tipo", "Largo", "Coordenadas"]);
  assert.equal(I.filasFicha(p)[1][1], "1,16 km");
  const u = { nombre: "Puente Angostura", clase: "puente", lat: 8.1445, lon: -63.5985, estado: "activa", bando: "azul" };
  assert.equal(I.enEjercicio([u], p), u);
  assert.equal(I.enEjercicio([{ ...u, lat: 8.3 }], p), null);
  assert.equal(I.enEjercicio([{ ...u, clase: "refineria" }], p), null);
});
