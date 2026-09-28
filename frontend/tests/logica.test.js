const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const U = (id, bando, extra = {}) => ({ id, bando, tipo: "terrestre", estado: "activa", lat: 0, lon: 0, ...extra });

test("pct redondea y muestra ? cuando el dato esta oculto por la niebla", () => {
  assert.equal(L.pct(49.6), "50%");
  assert.equal(L.pct(null), "?");
  assert.equal(L.pct(undefined), "?");
  assert.equal(L.pct(0), "0%");
});

test("fechaUtc interpreta como UTC las fechas del servidor sin zona", () => {
  assert.equal(L.fechaUtc("2026-09-24T21:00:00"), Date.UTC(2026, 8, 24, 21, 0, 0));
  assert.equal(L.fechaUtc("2026-09-24T21:00:00Z"), Date.UTC(2026, 8, 24, 21, 0, 0));
  assert.equal(L.fechaUtc("2026-09-24T21:00:00+02:00"), Date.UTC(2026, 8, 24, 19, 0, 0));
  assert.equal(L.fechaUtc(null), null);
  assert.equal(L.fechaUtc("basura"), null);
});

test("segundosRestantes corrige el desfase entre reloj del servidor y del cliente", () => {
  const servidor = "2026-09-24T21:00:00"; // hora del servidor al enviar el estado
  const relojClienteAlRecibir = Date.UTC(2026, 8, 24, 20, 55, 0); // el cliente va 5 min atrasado
  // el plazo vence 90 s despues de la hora del servidor; han pasado 30 s en el cliente
  const resto = L.segundosRestantes("2026-09-24T21:01:30", servidor, relojClienteAlRecibir, relojClienteAlRecibir + 30000);
  assert.equal(resto, 60);
});

test("segundosRestantes nunca es negativo y sin plazo devuelve null", () => {
  const t = Date.UTC(2026, 8, 24, 21, 0, 0);
  assert.equal(L.segundosRestantes("2026-09-24T20:00:00", "2026-09-24T21:00:00", t, t), 0);
  assert.equal(L.segundosRestantes(null, "2026-09-24T21:00:00", t, t), null);
});

test("formatoTiempo", () => {
  assert.equal(L.formatoTiempo(0), "00:00");
  assert.equal(L.formatoTiempo(75), "01:15");
  assert.equal(L.formatoTiempo(3725), "1:02:05");
  assert.equal(L.formatoTiempo(null), "");
});

test("objetivosDisponibles: enemigos para atacar, otras unidades propias (no bases) para apoyar", () => {
  const us = [
    U(1, "azul"), U(2, "azul"), U(3, "azul", { tipo: "base" }), U(4, "azul", { estado: "destruida" }),
    U(5, "rojo"), U(6, "rojo", { estado: "destruida" }),
  ];
  assert.deepEqual(L.objetivosDisponibles(us, "azul", "atacar", 1).map((u) => u.id), [5]);
  assert.deepEqual(L.objetivosDisponibles(us, "azul", "apoyar", 1).map((u) => u.id), [2]);
  assert.deepEqual(L.objetivosDisponibles(us, "rojo", "atacar", 5).map((u) => u.id), [1, 2, 3]);
});

test("unidadesConOrdenes excluye bases, destruidas y enemigas", () => {
  const us = [U(1, "azul"), U(2, "azul", { tipo: "base" }), U(3, "azul", { estado: "destruida" }), U(4, "rojo")];
  assert.deepEqual(L.unidadesConOrdenes(us, "azul").map((u) => u.id), [1]);
});

test("textoListos y etiquetaClima", () => {
  assert.equal(L.textoListos({ listo_azul: true, listo_rojo: false }), "Azul listo · Rojo pendiente");
  assert.equal(L.etiquetaClima("tormenta"), "Tormenta");
  assert.equal(L.etiquetaClima("raro"), "raro");
});

test("trayectorias ignora el ruido y las unidades nuevas", () => {
  const antes = [U(1, "azul", { lat: 8, lon: -70 }), U(2, "rojo", { lat: 9, lon: -71 })];
  const despues = [
    U(1, "azul", { lat: 8.2, lon: -70 }), U(2, "rojo", { lat: 9.0001, lon: -71 }), U(3, "rojo", { lat: 1, lon: 1 }),
  ];
  assert.deepEqual(L.trayectorias(antes, despues), [{ id: 1, bando: "azul", desde: [8, -70], hasta: [8.2, -70] }]);
});

test("lineasCombate une atacante y defensor y omite unidades desconocidas", () => {
  const us = [U(1, "azul", { lat: 1, lon: 2 }), U(2, "rojo", { lat: 3, lon: 4 })];
  const cs = [{ atacante_id: 1, defensor_id: 2 }, { atacante_id: 1, defensor_id: 99 }];
  const r = L.lineasCombate(cs, us);
  assert.equal(r.length, 1);
  assert.deepEqual([r[0].desde, r[0].hasta], [[1, 2], [3, 4]]);
});

test("describirCombate", () => {
  const c = { atacante: "A", defensor: "B", ratio: 1.234, perdida_atacante: 10.4, perdida_defensor: 24.6, efectos: "terreno montana x1.60" };
  assert.equal(L.describirCombate(c), "A → B: ratio 1.23, bajas 10/25 (terreno montana x1.60)");
  assert.equal(L.describirCombate({ ...c, efectos: "" }), "A → B: ratio 1.23, bajas 10/25");
});

test("turnosReproducibles descarta el turno en curso (sin instantanea)", () => {
  const inf = { turnos: [{ turno: 0, unidades: [U(1, "azul")] }, { turno: 1, unidades: [U(1, "azul")] }, { turno: 2, unidades: [] }] };
  assert.deepEqual(L.turnosReproducibles(inf).map((t) => t.turno), [0, 1]);
});
