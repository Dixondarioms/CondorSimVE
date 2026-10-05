const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("../static/js/replay.js");

const u = (id, bando, lat, lon, extra = {}) => ({ id, nombre: `U${id}`, bando, tipo: "terrestre", clase: "infanteria", lat, lon, fuerza: 100, estado: "activa", ...extra });
const turno = (n, unidades, extra = {}) => ({ turno: n, clima: "despejado", unidades, combates: [], eventos: [], marcador: { azul: { total: 0 }, rojo: { total: 0 } }, ...extra });

// tres instantaneas: U1 avanza al norte; U2 (roja) queda fija y es destruida en el turno 2; U3 aparece en el turno 2
const TURNOS = [
  turno(0, [u(1, "azul", 0, 0), u(2, "rojo", 1, 1)]),
  turno(1, [u(1, "azul", 0.5, 0), u(2, "rojo", 1, 1, { fuerza: 60 })], {
    combates: [{ id: 1, atacante_id: 1, defensor_id: 2, atacante: "U1", defensor: "U2", lat: 1, lon: 1, perdida_atacante: 5, perdida_defensor: 40 }],
  }),
  turno(2, [u(1, "azul", 1, 0), u(2, "rojo", 1, 1, { fuerza: 0, estado: "destruida" }), u(3, "azul", 2, 2)], {
    clima: "lluvia", marcador: { azul: { total: 9 }, rojo: { total: 0 } },
    eventos: [{ id: 1, tipo: "clima", descripcion: "El clima cambia a lluvia." }],
  }),
];

test("la interpolacion va de la posicion del turno N a la del N+1 con arranque y frenado suaves", () => {
  const a = { lat: 0, lon: 0 };
  const b = { lat: 1, lon: 2 };
  assert.deepEqual(R.interpolar(a, b, 0), [0, 0]);
  assert.deepEqual(R.interpolar(a, b, 1), [1, 2]);
  assert.deepEqual(R.interpolar(a, b, 0.5), [0.5, 1]);
  const [lat25] = R.interpolar(a, b, 0.25);
  assert.ok(lat25 > 0 && lat25 < 0.25, "al principio avanza mas despacio que en linea recta");
  assert.equal(R.suavizar(-1), 0);
  assert.equal(R.suavizar(2), 1);
});

test("el estado en un instante entero coincide con la instantanea", () => {
  const e = R.estadoEnInstante(TURNOS, 1);
  assert.equal(e.indice, 1);
  assert.equal(e.fraccion, 0);
  assert.equal(e.destino, 1);
  assert.equal(e.turno.turno, 1);
  const u1 = e.unidades.find((x) => x.id === 1);
  assert.deepEqual([u1.lat, u1.lon, u1.opacidad], [0.5, 0, 1]);
  assert.equal(e.combates.length, 1, "los combates del turno se muestran al detenerse en el");
  assert.equal(e.unidades.length, 2);
});

test("a mitad de camino las unidades estan entre ambas instantaneas y se ven los combates del turno destino", () => {
  const e = R.estadoEnInstante(TURNOS, 0.5);
  assert.equal(e.indice, 0);
  assert.equal(e.destino, 1);
  const u1 = e.unidades.find((x) => x.id === 1);
  assert.equal(u1.lat, 0.25);
  assert.equal(u1.lon, 0);
  assert.equal(u1.fuerza, 100);
  const u2 = e.unidades.find((x) => x.id === 2);
  assert.equal(u2.fuerza, 80, "la fuerza tambien se interpola");
  assert.equal(e.combates[0].id, 1);
  assert.equal(e.unidades.length, 2, "U3 aun no existe");
});

test("las unidades destruidas se desvanecen y las nuevas se materializan durante la transicion", () => {
  const e = R.estadoEnInstante(TURNOS, 1.5);
  const u2 = e.unidades.find((x) => x.id === 2);
  assert.ok(u2.opacidad < 1 && u2.opacidad > R.OPACIDAD_DESTRUIDA);
  assert.equal(u2.desvaneciendo, true);
  assert.equal(u2.estado, "destruida");
  const u3 = e.unidades.find((x) => x.id === 3);
  assert.equal(u3.opacidad, 0.5);
  assert.deepEqual([u3.lat, u3.lon], [2, 2]);
  const fin = R.estadoEnInstante(TURNOS, 2);
  assert.equal(fin.unidades.find((x) => x.id === 2).opacidad, R.OPACIDAD_DESTRUIDA);
  assert.equal(fin.unidades.find((x) => x.id === 3).opacidad, 1);
});

test("una unidad que desaparece en la instantanea siguiente se desvanece", () => {
  const turnos = [turno(0, [u(1, "azul", 0, 0), u(9, "azul", 3, 3)]), turno(1, [u(1, "azul", 1, 0)])];
  const e = R.estadoEnInstante(turnos, 0.75);
  const u9 = e.unidades.find((x) => x.id === 9);
  assert.equal(u9.opacidad, 0.25);
  assert.equal(u9.desvaneciendo, true);
  assert.equal(R.estadoEnInstante(turnos, 1).unidades.length, 1);
});

test("el instante se acota al rango de turnos y la lista vacia no rompe", () => {
  assert.equal(R.estadoEnInstante(TURNOS, -3).indice, 0);
  const e = R.estadoEnInstante(TURNOS, 99);
  assert.equal(e.indice, 2);
  assert.equal(e.fraccion, 0);
  assert.equal(R.estadoEnInstante(TURNOS, NaN).indice, 0);
  assert.deepEqual(R.estadoEnInstante([], 1).unidades, []);
  assert.deepEqual(R.estelas([], 1), []);
});

test("el destello del combate pulsa y se apaga al final de la transicion", () => {
  assert.ok(R.intensidadCombate(0) < 0.05);
  const valores = [0.08, 0.17, 0.25, 0.33, 0.42, 0.5].map(R.intensidadCombate);
  assert.ok(Math.max(...valores) > 0.8, "hay picos");
  assert.ok(Math.min(...valores) < 0.2, "y valles");
  assert.ok(R.intensidadCombate(1) < R.intensidadCombate(0.17), "al final pega menos");
  assert.ok(R.intensidadCombate(5) <= 1 && R.intensidadCombate(-1) >= 0);
});

test("las lineas de combate salen de la posicion interpolada del atacante hasta el lugar del combate", () => {
  const e = R.estadoEnInstante(TURNOS, 0.5);
  const [l] = R.lineasCombate(e.combates, e.unidades);
  assert.deepEqual(l.desde, [0.25, 0]);
  assert.deepEqual(l.hasta, [1, 1]);
  // sin lat/lon en el combate se usa la posicion del defensor; sin defensor ni lugar, no se dibuja
  const [l2] = R.lineasCombate([{ atacante_id: 1, defensor_id: 2 }], e.unidades);
  assert.deepEqual(l2.hasta, [1, 1]);
  assert.deepEqual(R.lineasCombate([{ atacante_id: 1, defensor_id: 77 }], e.unidades), []);
});

test("la estela acumula los puntos recorridos hasta el instante y termina en la posicion interpolada", () => {
  const [e1] = R.estelas(TURNOS, 1.5);
  assert.equal(e1.id, 1);
  assert.equal(e1.bando, "azul");
  assert.deepEqual(e1.puntos, [[0, 0], [0.5, 0], [0.75, 0]]);
  assert.equal(R.estelas(TURNOS, 1.5).length, 1, "U2 no se movio y U3 acaba de aparecer: sin estela");
  assert.deepEqual(R.estelas(TURNOS, 0)[0], undefined, "al inicio nadie se movio");
  const [fin] = R.estelas(TURNOS, 2);
  assert.deepEqual(fin.puntos, [[0, 0], [0.5, 0], [1, 0]], "en el ultimo turno no se duplica el punto final");
});

test("el avance depende del tiempo transcurrido y de la velocidad, sin pasarse del ultimo turno", () => {
  const n = TURNOS.length;
  assert.equal(R.avanzar(0, R.DURACION_TURNO_MS, 1, n), 1);
  assert.equal(R.avanzar(0, R.DURACION_TURNO_MS, 2, n), 2);
  assert.equal(R.avanzar(0, R.DURACION_TURNO_MS, 0.5, n), 0.5);
  assert.equal(R.avanzar(1.5, R.DURACION_TURNO_MS * 4, 4, n), 2);
  assert.equal(R.avanzar(0.5, -100, 1, n), 0.5, "un dt negativo no retrocede");
  assert.deepEqual(R.VELOCIDADES, [0.5, 1, 2, 4]);
});

test("la barra de progreso convierte ida y vuelta con el instante", () => {
  assert.equal(R.sliderMax(TURNOS.length), 2 * R.PASOS_SLIDER);
  assert.equal(R.sliderMax(0), 0);
  assert.equal(R.sliderDeTiempo(1.25), 1250);
  assert.equal(R.tiempoDeSlider("1250", TURNOS.length), 1.25);
  assert.equal(R.tiempoDeSlider("99999", TURNOS.length), 2);
  assert.equal(R.tiempoDeSlider("x", TURNOS.length), 0);
});

test("el rotulo resume turno, hora, clima y marcador; las novedades listan combates y eventos", () => {
  assert.equal(R.textoRotulo(TURNOS, R.estadoEnInstante(TURNOS, 0), 360), "Despliegue inicial · Despejado · Marcador azul 0 - rojo 0");
  const texto = R.textoRotulo(TURNOS, R.estadoEnInstante(TURNOS, 1.5), 360);
  assert.equal(texto, "Turno 2 de 2 · 07:00h · Lluvia · Marcador azul 9 - rojo 0");
  assert.equal(R.textoRotulo(TURNOS, R.estadoEnInstante([], 0), 360), "");
  assert.deepEqual(R.novedades(TURNOS[1]), ["U1 → U2: bajas 5/40"]);
  assert.deepEqual(R.novedades(TURNOS[2]), ["[clima] El clima cambia a lluvia."]);
  assert.deepEqual(R.novedades(null), []);
});

test("la zona de interes reune las estelas completas y los lugares de combate", () => {
  const zona = R.zonaDeInteres(TURNOS);
  assert.deepEqual(zona, [[0, 0], [0.5, 0], [1, 0], [1, 1]]);
  assert.deepEqual(R.zonaDeInteres([turno(0, [u(1, "azul", 0, 0)]), turno(1, [u(1, "azul", 0, 0)])]), [], "sin movimiento ni combates no se reencuadra");
});
