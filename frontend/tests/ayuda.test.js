const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const T = require("../static/js/ayuda_temas.js");
const R = require("../static/js/recorrido.js");

const HTML = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const primero = (q, director = false) => (T.buscar(q, { director })[0] || {}).id;

test("el buscador responde preguntas escritas con palabras comunes", () => {
  assert.equal(primero("¿cómo despego un caza?"), "despegar");
  assert.equal(primero("no veo al enemigo"), "no-veo");
  assert.equal(primero("qué hace el A-4"), "reparticiones");
  assert.equal(primero("cambiar la contraseña"), "entrar");
  assert.equal(primero("el círculo amarillo"), "contactos");
  assert.equal(primero("las estelas del mapa"), "capas");
  assert.equal(primero("interferir los radares enemigos"), "ge");
  assert.equal(primero("pausa automática"), "pausa-auto");
  assert.equal(primero("el reloj no avanza"), "reloj-quieto");
  assert.equal(primero("la foto del hellfire"), "fichas-armas");
  assert.deepEqual(T.buscar("", {}), []);
});

test("los temas del director solo aparecen al director", () => {
  assert.ok(!T.buscar("crear escenario desde plantilla").some((t) => t.director));
  assert.equal(primero("crear escenario desde plantilla", true), "preparar");
});

test("cada tema tiene seccion conocida, id unico y texto", () => {
  const ids = new Set();
  for (const t of T.TEMAS) {
    assert.ok(T.SECCIONES.includes(t.seccion), t.id);
    assert.ok(!ids.has(t.id), t.id);
    ids.add(t.id);
    assert.ok(t.titulo && t.claves && t.texto.length > 80, t.id);
  }
});

test("el recorrido apunta a partes que existen en la pantalla", () => {
  for (const p of R.PASOS) {
    if (!p.sel) continue;
    const id = (p.sel.match(/#([\w-]+)/) || [])[1];
    assert.ok(id && HTML.includes(`id="${id}"`), `${p.titulo}: ${p.sel}`);
    if (p.pestana) assert.ok(HTML.includes(`data-pestana="${p.pestana}"`), p.pestana);
  }
  assert.ok(HTML.includes('id="btn-ayuda"') && HTML.includes('id="dlg-ayuda"'));
});

test("el recorrido pasa por todas las pestanas y por las funciones nuevas", () => {
  const pestanas = new Set(R.PASOS.map((p) => p.pestana).filter(Boolean));
  for (const p of ["fuerzas", "situacion", "pmo", "consola"]) assert.ok(pestanas.has(p), p);
  const sels = R.PASOS.map((p) => p.sel || "").join(" ");
  for (const s of ["#sec-aviacion", "#sec-orden .modos", "#tarjeta-zonas", "#tarjeta-chat", "#tarjeta-alertas",
    "#panel-unidad", "#sec-eventos-auto", "#sec-trafico", "#btn-informe"]) assert.ok(sels.includes(s), s);
  const textos = R.PASOS.map((p) => p.texto).join(" ");
  for (const t of ["Interceptar", "Torpedo", "Minar", "Barrer minas", "Sonoboyas", "defensa de punto", "antimisil",
    "Carga de armamento", "Sistemas", "profundidad"]) assert.ok(textos.includes(t), t);
});

test("la practica del recorrido y la del ejercicio Tutorial del Condor tienen los mismos pasos", () => {
  const plantilla = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "backend", "data", "plantillas_sistema",
    "tutorial_condor.json"), "utf8"));
  const enDescripcion = (plantilla.descripcion.match(/\d+\) /g) || []).length;
  const ultimo = R.PASOS[R.PASOS.length - 1];
  const enRecorrido = (ultimo.texto.match(/<li>/g) || []).length;
  const tema = T.TEMAS.find((t) => t.id === "tutorial");
  assert.ok(enDescripcion >= 12);
  assert.equal(enRecorrido, enDescripcion);
  assert.equal((tema.texto.match(/<li>/g) || []).length, enDescripcion);
  assert.equal(primero("quiero practicar solo"), "tutorial");
});
