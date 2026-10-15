const test = require("node:test");
const assert = require("node:assert/strict");
const T = require("../static/js/tiem.js");

test("estado de cada documento con su turno", () => {
  assert.deepEqual(T.textoEstado({ estado: "borrador", existe: false }), { texto: "Sin empezar", clase: "" });
  assert.deepEqual(T.textoEstado({ estado: "borrador", existe: true }), { texto: "Borrador", clase: "" });
  assert.deepEqual(T.textoEstado({ estado: "presentado", existe: true, presentado_turno: 2 }), { texto: "Presentado (turno 2)", clase: "mov" });
  assert.deepEqual(T.textoEstado({ estado: "devuelto", existe: true, revisado_turno: 3 }), { texto: "Devuelto (turno 3)", clase: "fuego" });
  assert.equal(T.textoAvance({ a: { estado: "aprobado" }, b: { estado: "presentado" }, c: { estado: "borrador" }, d: { estado: "devuelto" } }),
    "1 de 4 aprobados · 1 presentado · 1 devuelto");
});

test("las ayudas solo completan los campos vacíos", () => {
  const { contenido, llenados } = T.completarVacios(
    { mision_to: "escrito por el alumno", prc: [], mision_especifica: { tarea: "", que: "" }, cog: [{ cog: "x" }] },
    { mision_to: "del PMO", prc: [{ factor: "Aviación" }], mision_especifica: { tarea: "Conducir" }, cog: [], nuevo: "" });
  assert.equal(contenido.mision_to, "escrito por el alumno");
  assert.deepEqual(contenido.prc, [{ factor: "Aviación" }]);
  assert.deepEqual(contenido.mision_especifica, { tarea: "Conducir" });
  assert.deepEqual(contenido.cog, [{ cog: "x" }]);
  assert.deepEqual(llenados.sort(), ["mision_especifica", "prc"]);
});

test("resumen APA de una forma de acción", () => {
  assert.equal(T.resumenApa({ naturaleza: "si", integridad: "parcial", oportunidad: "si", practicabilidad: "practicable", aceptabilidad: "alta" }),
    "Naturaleza Sí · Integridad Parcial · Oportunidad Sí · Practicable · Aceptabilidad alta");
  assert.equal(T.resumenApa({}), "");
  assert.equal(T.textoOpcion("operacional"), "Operacional");
  assert.equal(T.textoOpcion(""), "—");
});
