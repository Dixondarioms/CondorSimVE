const test = require("node:test");
const assert = require("node:assert/strict");
const Estelas = require("../static/js/estelas.js");
const ClimaMapa = require("../static/js/clima_mapa.js");

const KM = 1 / 111.2;

test("la estela recuerda por donde paso y olvida lo mas viejo que su duracion", () => {
  const e = Estelas.crear(600);
  for (let s = 0; s <= 1200; s += 60) e.registrar(1, (s / 60) * KM, 0, s);  // 1 km por minuto hacia el norte
  e.recortar(1200);
  const tramos = e.tramos(1, 1200);
  assert.ok(tramos.length >= 4);
  const lats = tramos.flatMap((t) => t.puntos.map((p) => p[0]));
  assert.ok(Math.min(...lats) >= 9 * KM && Math.max(...lats) <= 20 * KM + 1e-9);  // solo los ultimos 10 minutos
  assert.ok(tramos[0].opacidad < tramos[tramos.length - 1].opacidad);  // lo viejo, mas tenue
});

test("una unidad quieta no llena la estela y un traslado del director la empieza de nuevo", () => {
  const e = Estelas.crear(1800);
  for (let s = 0; s < 300; s += 10) e.registrar(2, 0, 0, s);
  assert.deepEqual(e.tramos(2, 300), []);
  e.registrar(2, 0, 2 * KM, 310);
  assert.equal(e.tramos(2, 310).length > 0, true);
  e.registrar(2, 3, 3, 320);  // ~470 km de golpe
  assert.deepEqual(e.tramos(2, 320), []);
});

test("recortar quita las unidades que ya no estan", () => {
  const e = Estelas.crear(1800);
  e.registrar(1, 0, 0, 0);
  e.registrar(3, 0, 0, 0);
  e.recortar(10, new Set([1]));
  assert.deepEqual(e.ids(), [1]);
});

test("la zona meteorologica sigue su deriva entre estado y estado, sin saltos", () => {
  const z = { lat: 0, lon: 0, deriva_rumbo: 90, deriva_kmh: 40 };
  assert.deepEqual(ClimaMapa.posicion(z, 3600, 3600), [0, 0]);
  const [lat, lon] = ClimaMapa.posicion(z, 3600 + 900, 3600);  // un cuarto de hora despues: 10 km al este
  assert.ok(Math.abs(lat) < 1e-9 && Math.abs(lon * 111.32 - 10) < 1e-6);
  assert.deepEqual(ClimaMapa.posicion({ ...z, deriva_kmh: 0 }, 9000, 0), [0, 0]);
});

test("el filtro de nubes se adapta al tamaño de la zona en pantalla", () => {
  const chica = ClimaMapa.filtroPara(15);
  const grande = ClimaMapa.filtroPara(400);
  assert.ok(chica.desplazamiento < grande.desplazamiento && chica.frecuencia > grande.frecuencia);
  assert.ok(grande.desplazamiento <= 70 && chica.desplazamiento >= 2);
  assert.deepEqual(Object.keys(ClimaMapa.CAPAS_NUBE).sort(), ["lluvia", "nublado", "tormenta"]);
});

test("un estado con la hora una fraccion atrasada no borra la estela", () => {
  const e = Estelas.crear(1800);
  e.registrar(4, 0, 0, 60.0);
  e.registrar(4, 1 * KM, 0, 120.0);
  e.registrar(4, 1.01 * KM, 0, 119.97);  // el estado completo, construido un instante antes
  e.registrar(4, 2 * KM, 0, 180.0);
  const pts = e.tramos(4, 180).flatMap((t) => t.puntos);
  assert.ok(pts.some((p) => p[0] === 0) && pts.some((p) => p[0] === 2 * KM));
});
