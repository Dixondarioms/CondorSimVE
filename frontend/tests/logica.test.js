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

test("escalaUnidad: las unidades se achican de lejos y crecen de cerca, dentro de un rango legible", () => {
  assert.equal(L.escalaUnidad(3), 0.35);
  assert.ok(L.escalaUnidad(6) < L.escalaUnidad(8) && L.escalaUnidad(8) < L.escalaUnidad(10));
  assert.ok(Math.abs(L.escalaUnidad(10) - 1.05) < 1e-9);
  assert.equal(L.escalaUnidad(18), 1.5);
  assert.ok(L.ZOOM_ROTULOS < L.ZOOM_ALCANCES);
});

test("unidadesConAlcance: solo las desplegadas con alcance (sin bases, misiles, embarcadas ni aviones en tierra)", () => {
  const u = (id, x) => ({ id, estado: "activa", tipo: "terrestre", clase: "infanteria", alcance_km: 5, lat: 8, lon: -70, transporte_id: null, en_tierra: false, ...x });
  const lista = [
    u(1), u(2, { tipo: "base", clase: "base_aerea" }), u(3, { tipo: "aerea", clase: "misil_crucero" }), u(4, { transporte_id: 9 }),
    u(5, { tipo: "aerea", clase: "caza", en_tierra: true }), u(6, { estado: "destruida" }), u(7, { alcance_km: 0 }), u(8, { tipo: "aerea", clase: "caza" }),
  ];
  assert.deepEqual(L.unidadesConAlcance(lista).map((x) => x.id), [1, 8]);
});

test("perfil de vuelo: textos y que sensores dibujan su cobertura por relieve", () => {
  assert.equal(L.textoPerfil("rasante"), "Rasante (60 m)");
  assert.equal(L.textoPerfil(null), "");
  const radar = { tipo: "terrestre", estado: "activa", deteccion_km: 150 };
  assert.ok(L.muestraCobertura(radar, { emisor: true }));
  assert.ok(L.muestraCobertura({ tipo: "naval", estado: "activa", deteccion_km: 30 }, { emisor: false }));
  assert.ok(!L.muestraCobertura({ tipo: "terrestre", estado: "activa", deteccion_km: 8 }, { emisor: false }));
  assert.ok(!L.muestraCobertura({ tipo: "aerea", estado: "activa", deteccion_km: 60 }, { emisor: false }));
  assert.ok(!L.muestraCobertura({ ...radar, estado: "destruida" }, { emisor: true }));
});

test("textoEtapa: etapa del contacto enemigo y su incertidumbre", () => {
  assert.equal(L.textoEtapa({ nombre: "A" }), "");
  assert.equal(L.textoEtapa({ etapa: "desconocido", incertidumbre_km: 2.34 }), "Contacto desconocido · posición ± 2,3 km");
  assert.equal(L.textoEtapa({ etapa: "identificado", incertidumbre_km: 0 }), "Contacto identificado");
  assert.equal(L.lineasTarjeta({ etapa: "clasificado", incertidumbre_km: 15.6, fuerza: null, tipo: "terrestre" }, null)[0], "Contacto clasificado · posición ± 16 km");
});

test("selector de aeronaves: solo aeronaves y filtro por texto (sin acentos) y por clase", () => {
  const ms = [
    { id: "at27", clase: "ataque", tipo: "aerea", nombre: "EMB-312 Tucano (AT-27)", corto: "AT-27", pais: "Brasil", fabricante: "Embraer", funcion: "Entrenador" },
    { id: "su35", clase: "caza", tipo: "aerea", nombre: "Su-35S Flanker-E", corto: "Su-35", pais: "Rusia", fabricante: "Sukhoi", funcion: "Caza" },
    { id: "t72b1", clase: "blindado", tipo: "terrestre", nombre: "T-72B1", corto: "T-72B1", pais: "Rusia", fabricante: "UVZ", funcion: "Tanque" },
    { id: "crucero", clase: "misil_crucero", tipo: "aerea", misil: true, nombre: "Tomahawk", corto: "Tomahawk", pais: "EE. UU.", fabricante: "Raytheon", funcion: "Misil" },
  ];
  assert.deepEqual(ms.filter(L.esAeronave).map((m) => m.id), ["at27", "su35"]);
  assert.equal(L.modeloDespegaDe(ms[2], null), false);  // un tanque no despega de una base
  assert.deepEqual(L.filtrarModelos(ms.filter(L.esAeronave), "rusia").map((m) => m.id), ["su35"]);
  assert.deepEqual(L.filtrarModelos(ms.filter(L.esAeronave), "tucano").map((m) => m.id), ["at27"]);
  assert.deepEqual(L.filtrarModelos(ms.filter(L.esAeronave), "", "caza").map((m) => m.id), ["su35"]);
});
