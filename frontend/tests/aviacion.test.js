const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const MODELOS = [
  { id: "f16", corto: "F-16", nombre: "F-16A/B Fighting Falcon" },
  { id: "su30", corto: "Su-30", nombre: "Su-30MK2 Flanker-G" },
];
const U = (extra) => ({ id: 1, bando: "azul", tipo: "aerea", clase: "caza", estado: "activa", fuerza: 100, lat: 10, lon: -67, ...extra });

test("modeloDe encuentra el modelo y devuelve null si no hay modelo o el enemigo no esta identificado", () => {
  assert.equal(L.modeloDe(U({ modelo: "su30" }), MODELOS).corto, "Su-30");
  assert.equal(L.modeloDe(U({ modelo: "" }), MODELOS), null);
  assert.equal(L.modeloDe(U({ modelo: null }), MODELOS), null); // enemigo detectado: el servidor oculta el modelo
  assert.equal(L.modeloDe(U({ modelo: "mig99" }), MODELOS), null);
  assert.equal(L.modeloDe(U({ modelo: "f16" }), undefined), null);
});

test("rotuloModelo: modelo y tamano del grupo, sin sufijo si es una sola aeronave", () => {
  assert.equal(L.rotuloModelo(U({ modelo: "f16", aeronaves: 4 }), MODELOS), "F-16 ×4");
  assert.equal(L.rotuloModelo(U({ modelo: "su30", aeronaves: 1 }), MODELOS), "Su-30");
  assert.equal(L.rotuloModelo(U({ modelo: null, aeronaves: null }), MODELOS), "");
});

test("aeronavesOperativas sigue la fuerza del grupo y nunca baja de 1 mientras siga vivo", () => {
  assert.equal(L.aeronavesOperativas(U({ aeronaves: 4, fuerza: 100 })), 4);
  assert.equal(L.aeronavesOperativas(U({ aeronaves: 4, fuerza: 50 })), 2);
  assert.equal(L.aeronavesOperativas(U({ aeronaves: 4, fuerza: 5 })), 1);
  assert.equal(L.aeronavesOperativas(U({ aeronaves: 4, fuerza: 0 })), 0);
  assert.equal(L.aeronavesOperativas(U({ aeronaves: null, fuerza: null })), null);
  assert.equal(L.aeronavesOperativas(U({ aeronaves: 4, fuerza: null })), null);
});

test("basesAereasPropias: solo bases aereas activas del bando y con fuerza suficiente", () => {
  const b = (id, extra) => U({ id, tipo: "base", clase: "base_aerea", ...extra });
  const lista = [
    b(1), b(2, { bando: "rojo" }), b(3, { estado: "destruida" }), b(4, { fuerza: 24 }), b(5, { fuerza: 25 }),
    b(6, { clase: "deposito" }), U({ id: 7 }),
  ];
  assert.deepEqual(L.basesAereasPropias(lista, "azul").map((u) => u.id), [1, 5]);
  assert.deepEqual(L.basesAereasPropias(lista, "rojo").map((u) => u.id), [2]);
});

test("detalleDespegue y textoDespegue leen el JSON de la orden y toleran datos rotos", () => {
  const o = { tipo: "despegar", detalle: JSON.stringify({ modelo: "su30", aeronaves: 4, indicativo: "Flecha 1" }) };
  assert.deepEqual(L.detalleDespegue(o), { modelo: "su30", aeronaves: 4, indicativo: "Flecha 1" });
  assert.equal(L.textoDespegue(o, MODELOS), "Despegar Su-30 ×4 «Flecha 1»");
  assert.equal(L.textoDespegue({ detalle: JSON.stringify({ modelo: "f16", aeronaves: 2 }) }, MODELOS), "Despegar F-16 ×2");
  assert.deepEqual(L.detalleDespegue({ detalle: "no es json" }), {});
  assert.deepEqual(L.detalleDespegue({ detalle: "3" }), {});
  assert.deepEqual(L.detalleDespegue(null), {});
  assert.equal(L.textoDespegue({ detalle: "" }, MODELOS), "Despegar grupo ×?");
});

test("aeronavesComprometidas suma las activas del bando y los despegues pendientes", () => {
  const unidades = [
    U({ id: 1, aeronaves: 4 }), U({ id: 2, aeronaves: 2 }), U({ id: 3, aeronaves: 8, bando: "rojo" }),
    U({ id: 4, aeronaves: 8, estado: "destruida" }), U({ id: 5, tipo: "terrestre", clase: "infanteria", aeronaves: 1 }),
    U({ id: 6, aeronaves: null }), // aeronave suelta sin tamano: cuenta como 1
  ];
  const ordenes = [
    { tipo: "despegar", estado: "pendiente", detalle: JSON.stringify({ aeronaves: 3 }) },
    { tipo: "despegar", estado: "resuelta", detalle: JSON.stringify({ aeronaves: 8 }) },
    { tipo: "mover", estado: "pendiente", detalle: "" },
  ];
  assert.equal(L.aeronavesComprometidas(unidades, ordenes, "azul"), 4 + 2 + 1 + 3);
  assert.equal(L.aeronavesComprometidas(unidades, [], "rojo"), 8);
});

test("baseEnEscenario detecta la base que ya esta en el punto (<= 2 km) y no cuenta las destruidas", () => {
  const base = U({ id: 9, tipo: "base", clase: "base_aerea", lat: 10.18, lon: -67.561 });
  assert.equal(L.baseEnEscenario([base], 10.18056, -67.56111).id, 9);
  assert.equal(L.baseEnEscenario([base], 10.30, -67.56), null);
  assert.equal(L.baseEnEscenario([{ ...base, estado: "destruida" }], 10.18056, -67.56111), null);
  assert.equal(L.baseEnEscenario([{ ...base, clase: "deposito" }], 10.18056, -67.56111), null);
});

test("nombreCortoBase quita 'Base Aérea' y el parentesis final", () => {
  assert.equal(L.nombreCortoBase("Base Aérea El Libertador"), "El Libertador");
  assert.equal(L.nombreCortoBase("Base Aérea Generalísimo Francisco de Miranda (La Carlota)"), "Generalísimo Francisco de Miranda");
  assert.equal(L.nombreCortoBase("Base Aerea Prueba"), "Prueba");
  assert.equal(L.nombreCortoBase(undefined), "");
});

test("nombreCortoBase tambien quita los sufijos en ingles de OurAirports (Airport, Air Force Base)", () => {
  assert.equal(L.nombreCortoBase("Punta Indio Naval Air Base"), "Punta Indio");
  assert.equal(L.nombreCortoBase("Whiteman Air Force Base"), "Whiteman");
  assert.equal(L.nombreCortoBase("Jorge Chávez International Airport"), "Jorge Chávez");
  assert.equal(L.nombreCortoBase("Aeropuerto Internacional Camilo Daza"), "Camilo Daza");
});

test("modoAerodromo: de lejos solo bases militares y curadas como puntos; aeropuertos desde el zoom 6; iconos desde el 8", () => {
  const militar = { tipo: "base aérea", origen: "ourairports" };
  const civil = { tipo: "aeropuerto", origen: "ourairports" };
  const curado = { tipo: "aeropuerto", origen: "curado" };
  assert.equal(L.modoAerodromo(militar, 4), "punto");
  assert.equal(L.modoAerodromo(curado, 4), "punto");
  assert.equal(L.modoAerodromo(civil, 4), null);
  assert.equal(L.modoAerodromo(civil, 5), null);
  assert.equal(L.modoAerodromo(civil, L.ZOOM_AEROPUERTOS), "punto");
  assert.equal(L.modoAerodromo(civil, L.ZOOM_ICONOS_AERODROMO), "icono");
  assert.equal(L.modoAerodromo(militar, 12), "icono");
});

test("colorAerodromo: color fijo del pais, si no el primer color oscuro de la bandera, si no el neutro", () => {
  const NACIONES = [
    { id: "peru", nombre: "Perú", colores: ["#D91023", "#FFFFFF"] },
    { id: "argentina", nombre: "Argentina", colores: ["#74ACDF", "#FFFFFF", "#F6B40E"] },
    { id: "colombia", nombre: "Colombia", colores: ["#FCD116", "#003893", "#CE1126"] },
  ];
  const FIJOS = { Venezuela: "#14213D", Colombia: "#8a6d00" };
  assert.equal(L.colorAerodromo("Venezuela", NACIONES, FIJOS), "#14213D");
  assert.equal(L.colorAerodromo("Colombia", NACIONES, FIJOS), "#8a6d00"); // el fijo manda sobre la bandera
  assert.equal(L.colorAerodromo("Perú", NACIONES, FIJOS), "#D91023");
  assert.equal(L.colorAerodromo("Argentina", NACIONES, FIJOS), "#3d4a57"); // celeste, blanco y amarillo: ninguno oscuro
  assert.equal(L.colorAerodromo("Guayana Francesa (Francia)", NACIONES, FIJOS), "#3d4a57");
  assert.equal(L.colorAerodromo("Perú", null, {}), "#3d4a57");
});
