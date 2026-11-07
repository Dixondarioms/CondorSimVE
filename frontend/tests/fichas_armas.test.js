const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const ficha = (id, extra = {}) => ({ id, nombre: id.toUpperCase(), tipo: "Misil", pais: "X", fabricante: "Y", guia: "Z",
  alcance: "8 km", velocidad: "Mach 1", ojiva: "9 kg", peso: "45 kg", descripcion: "d", foto: `/static/fotos/ref_arma_${id}.jpg`, ...extra });
const cat = {
  sistemas_da: { s400: {} },
  fichas_armas: {
    fichas: { agm114: ficha("agm114"), m230: ficha("m230"), hydra70: ficha("hydra70"), s8: ficha("s8"), gbu12: ficha("gbu12"),
      "48n6": ficha("48n6"), "9m96": ficha("9m96"), mk48: ficha("mk48"), natak: ficha("natak", { foto: null, peso: "—" }) },
    de_ota: { HLF: "agm114", CKH: "m230", CKL: "hydra70", BBU: "gbu12", BTK: "natak" },
    ota_modelo: { mi171sh: { CKL: "s8" } },
    por_modelo: { ah64e: ["agm114", "hydra70", "m230"], s400: ["48n6", "9m96"] },
    por_clase: { torpedo: ["mk48"] },
    sin_fichas: ["municion_merodeadora"],
  },
};

test("fichaDeCodigo: la del modelo (cohetes S-8 del Mi-171) o la general", () => {
  assert.equal(L.fichaDeCodigo(cat, "CKL", "mi171sh").id, "s8");
  assert.equal(L.fichaDeCodigo(cat, "CKL", "ah64e").id, "hydra70");
  assert.equal(L.fichaDeCodigo(cat, "NO", "ah64e"), null);
  assert.equal(L.fichaDeCodigo({}, "HLF", "ah64e"), null);
});

test("fichasDeUnidad: la carga de la aeronave, o lo que puede llevar su modelo", () => {
  const cargada = { tipo: "aerea", clase: "helicoptero", modelo: "ah64e", armamento: { quedan: { HLF: 8, CKH: 12, M999: 1 } } };
  const r = L.fichasDeUnidad(cargada, cat);
  assert.equal(r.titulo, "Armas de su carga");
  assert.deepEqual(r.fichas.map((f) => f.id), ["agm114", "m230"]);
  const sinCarga = L.fichasDeUnidad({ tipo: "aerea", clase: "helicoptero", modelo: "ah64e" }, cat);
  assert.equal(sinCarga.titulo, "Armas que puede llevar");
  assert.equal(sinCarga.fichas.length, 3);
});

test("fichasDeUnidad: sistema antiaéreo, clase sin modelo y municiones merodeadoras", () => {
  const da = L.fichasDeUnidad({ tipo: "terrestre", clase: "antiaerea", modelo: "s400" }, cat);
  assert.equal(da.titulo, "Armas del sistema");
  assert.deepEqual(da.fichas.map((f) => f.id), ["48n6", "9m96"]);
  assert.deepEqual(L.fichasDeUnidad({ tipo: "naval", clase: "torpedo" }, cat).fichas.map((f) => f.id), ["mk48"]);
  assert.equal(L.fichasDeUnidad({ tipo: "aerea", clase: "municion_merodeadora", modelo: "lucas", armamento: { quedan: { BBU: 1 } } }, cat), null);
  assert.equal(L.fichasDeUnidad({ tipo: "terrestre", clase: "infanteria" }, cat), null);
  assert.equal(L.fichasDeUnidad({ tipo: "terrestre", clase: "infanteria" }, {}), null);
});

test("fichasDeCarga y filasFichaArma", () => {
  assert.deepEqual(L.fichasDeCarga(cat, "ah64e", { HLF: 4, CKL: 4 }).map((f) => f.id), ["agm114", "hydra70"]);
  const filas = L.filasFichaArma(cat.fichas_armas.fichas.natak);
  assert.equal(filas[0][0], "Tipo");
  assert.ok(!filas.some(([k]) => k === "Peso")); // los datos que faltan («—») no se muestran
  assert.deepEqual(L.filasFichaArma(null), []);
});

test("familiaDeModelos: que catalogo de fotos abre cada clase al agregar una unidad", () => {
  assert.equal(L.familiaDeModelos({ tipo: "aerea" }), "aerea");
  assert.equal(L.familiaDeModelos({ tipo: "naval" }), "naval");
  assert.equal(L.familiaDeModelos({ tipo: "terrestre" }), "terrestre");
  assert.equal(L.familiaDeModelos({ tipo: "aerea", misil: true }), null); // misiles en vuelo: sin modelo que elegir
  assert.equal(L.familiaDeModelos({ tipo: "base" }), null);
  assert.equal(L.familiaDeModelos(null), null);
});

test("puedeLanzarMisiles: el misil del modelo manda sobre el de su clase", () => {
  const cat = { misiles_lanzador: { modelos: { molniya: "moskit", type052d: "yj18" }, sin_misiles: ["type42", "u209"] } };
  const fragata = { lanza_misiles: true };
  const patrullero = { lanza_misiles: false };
  const u = (modelo, clase) => ({ estado: "activa", modelo, clase });
  assert.equal(L.puedeLanzarMisiles(u("molniya", "patrullero"), patrullero, cat), true); // corbeta lanzamisiles
  assert.equal(L.puedeLanzarMisiles(u("guaicamacuto", "patrullero"), patrullero, cat), false);
  assert.equal(L.puedeLanzarMisiles(u("type42", "destructor"), fragata, cat), false); // sin misil antibuque
  assert.equal(L.puedeLanzarMisiles(u("arleigh_burke", "destructor"), fragata, cat), true);
  assert.equal(L.puedeLanzarMisiles(u("type42", "destructor"), fragata), true); // sin catalogo: la clase
});
