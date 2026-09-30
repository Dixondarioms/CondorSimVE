const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("climaEn: el peor entre el clima general y las zonas que cubren el punto", () => {
  const zonas = [{ tipo: "tormenta", lat: 0, lon: 0, radio_km: 30 }, { tipo: "lluvia", lat: 1, lon: 0, radio_km: 100 }];
  assert.equal(L.climaEn(0, 0, "nublado", zonas), "tormenta");
  assert.equal(L.climaEn(1, 0, "nublado", zonas), "lluvia");
  assert.equal(L.climaEn(5, 5, "nublado", zonas), "nublado");
  assert.equal(L.climaEn(0, 0, "tormenta", [{ tipo: "lluvia", lat: 0, lon: 0, radio_km: 30 }]), "tormenta");
  assert.equal(L.climaEn(0, 0, undefined, []), "despejado");
});

test("textoZonaClima describe tipo, radio, deriva y caducidad", () => {
  assert.equal(L.textoZonaClima({ tipo: "lluvia", nombre: "Frente 1", radio_km: 60, deriva_rumbo: 90, deriva_kmh: 25, hasta_turno: 8 }),
    "Lluvia Frente 1 · radio 60 km · deriva 25 km/h al E · hasta el turno 8");
  assert.equal(L.textoZonaClima({ tipo: "tormenta", nombre: "", radio_km: 35, deriva_rumbo: 0, deriva_kmh: 0, hasta_turno: null }),
    "Tormenta · radio 35 km · estacionaria · sin caducidad");
  assert.match(L.textoZonaClima({ tipo: "nublado", radio_km: 10, deriva_rumbo: 315, deriva_kmh: 10 }), /al NO/);
});
