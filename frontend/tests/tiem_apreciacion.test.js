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

test("ejes y celdas de la matriz de confrontación", () => {
  const ctx = { formas: ["F/A 1: Neutralizar", "F/A 2: Destruir"], capacidades: ["C1: Atacar"] };
  const celdas = [{ fa: "F/A 1: Neutralizar", capacidad: "C1: Atacar", efecto: "degrada", analisis: "x" },
    { fa: "F/A vieja", capacidad: "C9: Otra", efecto: "anula", analisis: "" }];
  assert.deepEqual(T.ejesMatriz(celdas, ctx), {
    filas: ["F/A 1: Neutralizar", "F/A 2: Destruir", "F/A vieja"], columnas: ["C1: Atacar", "C9: Otra"] });
  assert.equal(T.celdaDe(celdas, "F/A 1: Neutralizar", "C1: Atacar").efecto, "degrada");
  assert.deepEqual(T.celdaDe(celdas, "F/A 2: Destruir", "C1: Atacar"), { fa: "F/A 2: Destruir", capacidad: "C1: Atacar", efecto: "", analisis: "" });
  assert.deepEqual(T.ejesMatriz([], null), { filas: [], columnas: [] });
});

test("los documentos se agrupan por paso del TIEM", () => {
  const defs = { a: { paso: "Fase I · Paso 1" }, b: { paso: "Fase I · Paso 1" }, c: { paso: "Fase I · Paso 2" } };
  assert.deepEqual(T.porPaso(["a", "b", "c"], defs), [{ paso: "Fase I · Paso 1", tipos: ["a", "b"] }, { paso: "Fase I · Paso 2", tipos: ["c"] }]);
});
