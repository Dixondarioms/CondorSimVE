const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const NACIONES = [
  { id: "venezuela", nombre: "Venezuela" }, { id: "colombia", nombre: "Colombia" }, { id: "brasil", nombre: "Brasil" },
];
const esc = (nacion_azul, nacion_rojo) => ({ nacion_azul, nacion_rojo });

test("nacionDe devuelve la nacion del bando o null si no tiene o es desconocida", () => {
  assert.equal(L.nacionDe("azul", esc("venezuela", "colombia"), NACIONES).nombre, "Venezuela");
  assert.equal(L.nacionDe("rojo", esc("venezuela", "colombia"), NACIONES).nombre, "Colombia");
  assert.equal(L.nacionDe("rojo", esc("venezuela", ""), NACIONES), null);
  assert.equal(L.nacionDe("rojo", esc("venezuela", "marte"), NACIONES), null);
  assert.equal(L.nacionDe("azul", null, NACIONES), null);
  assert.equal(L.nacionDe("azul", esc("venezuela", ""), null), null);
  assert.equal(L.nacionDe("instructor", esc("venezuela", "colombia"), NACIONES), null);
});

test("etiquetaBandoNacion antepone Azul/Rojo y agrega el pais entre parentesis si lo tiene", () => {
  assert.equal(L.etiquetaBandoNacion("azul", esc("venezuela", ""), NACIONES), "Azul (Venezuela)");
  assert.equal(L.etiquetaBandoNacion("rojo", esc("venezuela", "brasil"), NACIONES), "Rojo (Brasil)");
  assert.equal(L.etiquetaBandoNacion("rojo", esc("venezuela", ""), NACIONES), "Rojo");
  assert.equal(L.etiquetaBandoNacion("azul", esc("", ""), NACIONES), "Azul");
  assert.equal(L.etiquetaBandoNacion("rojo", esc("venezuela", "colombia"), null), "Rojo");
  // dos bandos pueden representar al mismo pais (dos vecinos enfrentados, sin que intervenga Venezuela)
  assert.equal(L.etiquetaBandoNacion("azul", esc("colombia", "colombia"), NACIONES), "Azul (Colombia)");
  assert.equal(L.etiquetaBandoNacion("rojo", esc("colombia", "colombia"), NACIONES), "Rojo (Colombia)");
});
