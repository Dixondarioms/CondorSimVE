const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const caza = { id: 1, bando: "azul", tipo: "aerea", clase: "caza", estado: "activa", en_tierra: false };
const fragata = { id: 2, bando: "azul", tipo: "naval", clase: "fragata", estado: "activa" };
const bandido = { id: 10, bando: "rojo", tipo: "aerea", clase: "caza", estado: "activa", en_tierra: false };
const enTierra = { id: 11, bando: "rojo", tipo: "aerea", clase: "caza", estado: "activa", en_tierra: true };
const buque = { id: 12, bando: "rojo", tipo: "naval", clase: "fragata", estado: "activa" };
const tanque = { id: 13, bando: "rojo", tipo: "terrestre", clase: "blindado", estado: "activa" };
const misil = { id: 14, bando: "rojo", tipo: "aerea", clase: "misil_crucero", estado: "activa" };
const todas = [caza, fragata, bandido, enTierra, buque, tanque, misil];

test("interceptar: aeronaves en vuelo y buques; un buque solo contra buques", () => {
  assert.deepEqual(L.objetivosDisponibles(todas, "azul", "interceptar", 1).map((u) => u.id), [10, 12]);
  assert.deepEqual(L.objetivosDisponibles(todas, "azul", "interceptar", 2).map((u) => u.id), [12]);
});

test("textoIntercepcion: la cola muestra la acción y la fase", () => {
  assert.equal(L.textoIntercepcion(JSON.stringify({ accion: "seguir", fase: "contacto" }), "Bandido"),
    "Interceptar a Bandido (identificar y seguir) · fase: contacto");
  assert.equal(L.textoIntercepcion("", "Bandido"), "Interceptar a Bandido (identificar y neutralizar)");
});

test("textoEstimacionIntercepcion: alcance, tiempo, combustible e identificación", () => {
  const t = L.textoEstimacionIntercepcion({ alcanzable: true, minutos: 7, hora: "06:07", km: 105, combustible_llegada: 88.4,
    combustible_regreso: 70.2, base: "BA Libertador", velocidad_blanco_kmh: 800, velocidad_propia_kmh: 900, identifica: true, armas: "restringido" });
  assert.match(t, /Lo alcanza en 7 min \(a las 06:07\), a 105 km; llega con 88 %/);
  assert.match(t, /volver a BA Libertador le quedaría 70 %/);
  assert.match(t, /Armas restringidas/);
  assert.match(L.textoEstimacionIntercepcion({ alcanzable: false, velocidad_blanco_kmh: 1000, velocidad_propia_kmh: 500, motivo: "Se aleja." }), /Se aleja\./);
  assert.equal(L.textoEstimacionIntercepcion({ motivo_no: "Solo las aeronaves y los buques interceptan." }), "Solo las aeronaves y los buques interceptan.");
});
