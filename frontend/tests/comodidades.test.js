const test = require("node:test");
const assert = require("node:assert/strict");
const I = require("../static/js/interfaz.js");

test("cada alerta cae en su filtro", () => {
  assert.equal(I.grupoAlerta({ causa: "ataque" }), "ataques");
  assert.equal(I.grupoAlerta({ causa: "contacto" }), "contactos");
  assert.equal(I.grupoAlerta({ causa: "evento" }), "director");
  assert.equal(I.grupoAlerta({}), "otras");
  assert.ok(I.pasaFiltro({ causa: "zona" }, "contactos") && !I.pasaFiltro({ causa: "zona" }, "ataques"));
  assert.ok(I.pasaFiltro({ causa: "zona" }, "todas") && I.pasaFiltro({}, undefined));
});

test("los atajos no se disparan al escribir ni con una ventana abierta, y el reloj es del director", () => {
  const tecla = (key, tag = "DIV", extra = {}) => ({ key, target: { tagName: tag }, ...extra });
  assert.equal(I.accionDeTecla(tecla("m"), false, false), "mover");
  assert.equal(I.accionDeTecla(tecla("I"), false, false), "interceptar");
  assert.equal(I.accionDeTecla(tecla("m", "INPUT"), false, false), null);
  assert.equal(I.accionDeTecla(tecla("m"), false, true), null);
  assert.equal(I.accionDeTecla(tecla("m", "DIV", { ctrlKey: true }), false, false), null);
  assert.equal(I.accionDeTecla(tecla(" "), false, false), null);
  assert.equal(I.accionDeTecla(tecla(" "), true, false), "marcha");
  assert.equal(I.accionDeTecla(tecla("3"), true, false), "vel-60");
  assert.ok(I.ATAJOS.length >= 8 && I.FILTROS[0][0] === "todas");
});
