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

test("Orden de Operaciones: lo que vence ahora y lo de las próximas 24 horas", () => {
  assert.equal(T.refH(5, 3), "H+2");
  assert.equal(T.refH(3, 3), "H");
  assert.equal(T.refH(1, 3), "H-2");
  assert.equal(T.refH(4, null), "");
  const tareas = [
    { id: "a", turno: 2, tipo: "mover" }, { id: "b", turno: 3, tipo: "atacar" }, { id: "c", turno: 4, tipo: "mover" },
    { id: "d", turno: 40, tipo: "mover" }, { id: "e", turno: 1, tipo: "mover" }, { id: "f", turno: null }];
  const ej = { a: { estado: "rechazada", turno: 2, motivo: "x" }, e: { estado: "emitida", turno: 1 } };
  const r = T.ordenDelDia(tareas, ej, 3);
  assert.deepEqual(r.vencen.map((x) => [x.tarea.id, x.estado]), [["a", "rechazada"], ["b", "pendiente"]]);
  assert.deepEqual(r.proximas.map((x) => x.tarea.id), ["c"]);  // la del turno 40 queda fuera de las 24 h
  assert.equal(T.textoTarea({ tipo: "atacar", unidad_nombre: "A", objetivo_nombre: "R1" }, { atacar: "Atacar" }), "Atacar con A a R1");
  assert.equal(T.textoTarea({ tipo: "mover", unidad_nombre: "A", objetivo_nombre: "el puente" }, { mover: "Desplazar" }), "Desplazar con A hacia el puente");
});

test("supervisión: tareas del plan y órdenes fragmentarias, y renglón del registro", () => {
  const docs = { plan_operaciones: { contenido: { tareas: [{ id: "p1", turno: 2 }] } },
    supervision: { contenido: { ordenes_fragmentarias: [{ id: "f1", turno: 3 }] } } };
  assert.deepEqual(T.tareasDelBando(docs).map((t) => [t.id, t.origen]), [["p1", "plan"], ["f1", "frago"]]);
  assert.deepEqual(T.tareasDelBando({}), []);
  assert.deepEqual(T.renglonRegistro({ turno: 4, objetivo: "Atacar R1", resultado: "Rechazada", diferencia: "No se ejecutó", causa_sugerida: "Sin combustible" }),
    { turno: "4", objetivo: "Atacar R1", resultado: "Rechazada", diferencia: "No se ejecutó", causa: "Sin combustible", accion: "", responsable: "", estado: "abierta" });
});

test("la nota del instructor aparece en el estado del documento", () => {
  assert.equal(T.textoEstado({ estado: "aprobado", existe: true, revisado_turno: 3, nota: 17 }).texto, "Aprobado (turno 3) · 17/20");
});
