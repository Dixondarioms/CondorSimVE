const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const U = (id, bando, extra = {}) => ({
  id, bando, nombre: `U${id}`, tipo: "terrestre", clase: "infanteria", estado: "activa", lat: 0, lon: 0,
  fuerza: 100, combustible: 100, municion: 100, ...extra,
});
const estado = (unidades, extra = {}) => ({
  vista: extra.vista || "azul", escenario: { turno_actual: extra.turno || 1 }, unidades, contactos: [],
  ordenes: extra.ordenes || [], eventos: extra.eventos || [],
});

test("ramaDe agrupa por clase y cae al tipo cuando no hay clase", () => {
  assert.equal(L.ramaDe({ clase: "blindado", tipo: "terrestre" }), "blindados");
  assert.equal(L.ramaDe({ clase: "reconocimiento", tipo: "terrestre" }), "infanteria");
  assert.equal(L.ramaDe({ clase: "antiaerea", tipo: "terrestre" }), "artilleria");
  assert.equal(L.ramaDe({ clase: "caza", tipo: "aerea" }), "aviacion");
  assert.equal(L.ramaDe({ clase: "fragata", tipo: "naval" }), "naval");
  assert.equal(L.ramaDe({ clase: "puerto", tipo: "base" }), "bases");
  assert.equal(L.ramaDe({ clase: "", tipo: "aerea" }), "aviacion");
  assert.equal(L.ramaDe({ clase: "rara", tipo: "base" }), "bases");
});

test("agruparPorRama respeta el orden fijo y omite ramas vacias", () => {
  const us = [U(1, "azul", { clase: "caza", tipo: "aerea" }), U(2, "azul"), U(3, "azul", { clase: "artilleria" }), U(4, "azul")];
  const g = L.agruparPorRama(us);
  assert.deepEqual(g.map((x) => x.rama), ["infanteria", "artilleria", "aviacion"]);
  assert.deepEqual(g[0].unidades.map((u) => u.id), [2, 4]);
  assert.equal(g[0].nombre, "Infantería");
  assert.deepEqual(L.agruparPorRama([]), []);
});

test("horaSimulada avanza 1 h por turno y marca el cambio de dia", () => {
  assert.deepEqual(L.horaSimulada(360, 1), { texto: "06:00h", dia: 0 });
  assert.deepEqual(L.horaSimulada(360, 9), { texto: "14:00h", dia: 0 });
  assert.deepEqual(L.horaSimulada(13 * 60 + 30, 4), { texto: "16:30h", dia: 0 });
  assert.deepEqual(L.horaSimulada(23 * 60, 3), { texto: "01:00h", dia: 1 });
  assert.deepEqual(L.horaSimulada(undefined, 1), { texto: "06:00h", dia: 0 });
  assert.equal(L.textoHora(L.horaSimulada(23 * 60, 3)), "01:00h (D+1)");
});

test("efectosClima y visibilidadPct coinciden con el motor", () => {
  assert.equal(L.visibilidadPct("despejado"), 100);
  assert.equal(L.visibilidadPct("lluvia"), 70);
  assert.equal(L.visibilidadPct("tormenta"), 50);
  assert.equal(L.visibilidadPct("inventado"), 100);
  assert.equal(L.efectosClima("lluvia").terrestre, 0.8);
  assert.equal(L.efectosClima("tormenta").ataqueAereo, 0.5);
});

test("etiquetaBando", () => {
  assert.equal(L.etiquetaBando("azul"), "AZUL (ALUMNO)");
  assert.equal(L.etiquetaBando("rojo", "completa"), "ROJO (ALUMNO)");
  assert.equal(L.etiquetaBando("instructor", "completa"), "INSTRUCTOR");
  assert.equal(L.etiquetaBando("instructor", "rojo"), "INSTRUCTOR · VISTA ROJO");
  assert.equal(L.etiquetaBando("observador"), "OBSERVADOR");
});

test("claseBarra", () => {
  assert.equal(L.claseBarra(80), "");
  assert.equal(L.claseBarra(45), "bajo");
  assert.equal(L.claseBarra(10), "critico");
  assert.equal(L.claseBarra(null), "oculto");
});

test("estadoUnidad", () => {
  const pend = [{ unidad_id: 1, tipo: "mover" }, { unidad_id: 2, tipo: "atacar" }];
  assert.deepEqual(L.estadoUnidad(U(1, "azul"), pend), { texto: "Orden: mover", clase: "mov" });
  assert.deepEqual(L.estadoUnidad(U(2, "azul"), pend), { texto: "Orden: atacar", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad(U(3, "azul"), pend), { texto: "Operativa", clase: "ok" });
  assert.deepEqual(L.estadoUnidad(U(3, "azul", { estado: "destruida" })), { texto: "Destruida", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad(U(3, "rojo", { fuerza: null })), { texto: "Detectada", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad(U(3, "azul", { combustible: 0 })), { texto: "Sin combustible", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad(U(3, "azul", { municion: 0 })), { texto: "Sin munición", clase: "fuego" });
  assert.deepEqual(L.estadoUnidad(U(3, "azul", { tipo: "base" })), { texto: "Base operativa", clase: "ok" });
});

test("la primera vez solo se memoriza: no hay alertas", () => {
  const d = estado([U(1, "azul"), U(2, "rojo", { fuerza: null })], { eventos: [{ id: 5, tipo: "clima", descripcion: "El clima cambia" }] });
  const { alertas, memoria } = L.alertasNuevas(L.memoriaVacia(), d, "azul");
  assert.deepEqual(alertas, []);
  assert.equal(memoria.inicializada, true);
  assert.ok("2" in memoria.enemigos);
  assert.deepEqual(memoria.eventos, [5]);
});

test("detecta enemigos nuevos, los pierde de vista y avisa de las bajas", () => {
  let mem = L.alertasNuevas(L.memoriaVacia(), estado([U(1, "azul")]), "azul").memoria;

  let r = L.alertasNuevas(mem, estado([U(1, "azul"), U(2, "rojo", { fuerza: null })], { turno: 2 }), "azul");
  assert.deepEqual(r.alertas.map((a) => [a.nivel, a.texto]), [["critica", "Unidad enemiga detectada: U2 (infanteria)"]]);
  assert.equal(r.alertas[0].turno, 2);

  mem = r.memoria;
  r = L.alertasNuevas(mem, estado([U(1, "azul"), U(2, "rojo", { fuerza: null })], { turno: 3 }), "azul");
  assert.deepEqual(r.alertas, [], "el mismo enemigo no vuelve a alertar");

  mem = r.memoria;
  r = L.alertasNuevas(mem, estado([U(1, "azul")], { turno: 4 }), "azul");
  assert.deepEqual(r.alertas.map((a) => a.texto), ["Se perdió contacto con U2"]);

  r = L.alertasNuevas(r.memoria, estado([U(1, "azul"), U(2, "rojo", { fuerza: null })], { turno: 5 }), "azul");
  assert.equal(r.alertas.length, 1, "si reaparece, se vuelve a detectar");

  r = L.alertasNuevas(r.memoria, estado([U(1, "azul", { estado: "destruida" }), U(2, "rojo", { estado: "destruida", fuerza: null })], { turno: 6 }), "azul");
  assert.deepEqual(r.alertas.map((a) => a.texto).sort(), ["U1 fue destruida", "U2 fue destruida"]);
});

test("avisa una sola vez de combustible o municion bajos y rearma al reabastecer", () => {
  let mem = L.alertasNuevas(L.memoriaVacia(), estado([U(1, "azul")]), "azul").memoria;
  let r = L.alertasNuevas(mem, estado([U(1, "azul", { combustible: 20 })]), "azul");
  assert.deepEqual(r.alertas.map((a) => a.texto), ["U1: combustible 20%, necesita reabastecerse"]);
  r = L.alertasNuevas(r.memoria, estado([U(1, "azul", { combustible: 15 })]), "azul");
  assert.deepEqual(r.alertas, []);
  r = L.alertasNuevas(r.memoria, estado([U(1, "azul", { combustible: 100 })]), "azul");
  assert.deepEqual(r.alertas, []);
  r = L.alertasNuevas(r.memoria, estado([U(1, "azul", { municion: 10 })]), "azul");
  assert.deepEqual(r.alertas.map((a) => a.texto), ["U1: munición 10%, necesita reabastecerse"]);
  // las bases no alertan
  r = L.alertasNuevas(L.memoriaVacia(), estado([U(9, "azul", { tipo: "base", combustible: 0 })]), "azul");
  r = L.alertasNuevas(r.memoria, estado([U(9, "azul", { tipo: "base", combustible: 0 })]), "azul");
  assert.deepEqual(r.alertas, []);
});

test("eventos y resultado de ordenes generan alertas con su nivel", () => {
  const base = estado([U(1, "azul")], { ordenes: [{ id: 7, unidad_id: 1, tipo: "atacar", estado: "pendiente", resultado: "" }] });
  let mem = L.alertasNuevas(L.memoriaVacia(), base, "azul").memoria;
  const sig = estado([U(1, "azul")], {
    turno: 2,
    ordenes: [{ id: 7, unidad_id: 1, tipo: "atacar", estado: "resuelta", resultado: "Ratio 1.20" }],
    eventos: [{ id: 9, tipo: "logistica", descripcion: "Se perdio un caza" }, { id: 8, tipo: "clima", descripcion: "El clima cambia a lluvia." }],
  });
  const r = L.alertasNuevas(mem, sig, "azul");
  assert.deepEqual(r.alertas.map((a) => [a.nivel, a.texto]), [
    ["info", "El clima cambia a lluvia."], ["aviso", "Se perdio un caza"], ["info", "Orden resuelta (U1, atacar): Ratio 1.20"],
  ]);
  const rech = { ...sig, ordenes: [{ id: 7, unidad_id: 1, tipo: "atacar", estado: "rechazada", resultado: "Sin municion." }], eventos: [] };
  const r2 = L.alertasNuevas(mem, rech, "azul");
  assert.equal(r2.alertas[0].nivel, "aviso");
});

test("en vista completa no hay alertas de deteccion, pero si de bajas de ambos bandos", () => {
  const completa = (us, turno = 1) => ({ ...estado(us, { vista: "completa", turno }) });
  let r = L.alertasNuevas(L.memoriaVacia(), completa([U(1, "azul"), U(2, "rojo")]), "instructor");
  r = L.alertasNuevas(r.memoria, completa([U(1, "azul"), U(2, "rojo", { estado: "destruida" }), U(3, "rojo")], 2), "instructor");
  assert.deepEqual(r.alertas.map((a) => a.texto), ["U2 fue destruida"]);
});

test("alertasNuevas no modifica la memoria recibida", () => {
  const mem = L.alertasNuevas(L.memoriaVacia(), estado([U(1, "azul")]), "azul").memoria;
  const copia = JSON.stringify(mem);
  L.alertasNuevas(mem, estado([U(1, "azul", { combustible: 5 }), U(2, "rojo", { fuerza: null })]), "azul");
  assert.equal(JSON.stringify(mem), copia);
});
