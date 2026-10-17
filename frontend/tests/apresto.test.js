const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

const r = {
  grado_nombre: "Elevado Apresto Operacional", fase_nombre: "naranja", config: { grado: "elevado", fase: 2 },
  aeronaves_listas_pct: 80, reservas_incorporadas: false, tienen: 3, total: 5,
};

test("linea del grado de apresto del bando", () => {
  assert.strictEqual(Logica.textoGradoApresto(r), "Elevado Apresto Operacional (fase naranja) · aeronaves listas 80 % · "
    + "reservas y milicia sin incorporar (evento 2 de la PCAO) · 3 de 5 unidades con apresto.");
  assert.strictEqual(Logica.textoGradoApresto(null), "");
});

test("fila del cuadro de apresto marca lo que esta bajo el minimo", () => {
  const minimos = { personal: 75, armamento: 90, equipamiento: 85, adiestramiento: 85, c3: 90 };
  const f = { nombre: "Escuadrilla F-16", tiene: false, aspectos: { personal: 80, armamento: 100, equipamiento: 60, adiestramiento: 90, c3: 100 } };
  const fila = Logica.filaApresto(f, minimos);
  assert.strictEqual(fila[0], "Escuadrilla F-16");
  assert.deepStrictEqual(fila[3], { texto: "60", bajo: true });
  assert.deepStrictEqual(fila[1], { texto: "80", bajo: false });
  assert.strictEqual(fila[6], "No");
});

test("eventos de la PCAO", () => {
  const p = { eventos: [{ nombre: "1. Activación del plan de localización (aviso)", plazo: 2, estado: "cumplido" },
    { nombre: "2. Incorporación del personal y los recursos", plazo: 1, estado: "en curso" }] };
  assert.deepStrictEqual(Logica.lineasPcao(p), ["1. Activación del plan de localización (aviso) · 2 turnos · cumplido",
    "2. Incorporación del personal y los recursos · 1 turno · en curso"]);
});
