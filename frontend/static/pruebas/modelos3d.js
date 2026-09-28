/* Hoja de contacto de los modelos 3D: cada modelo a varios rumbos, en formacion y al tamaño real del mapa. */
(() => {
  "use strict";
  const hoja = document.getElementById("hoja");
  const seccion = (titulo, items) => {
    const s = document.createElement("section");
    const h = document.createElement("b");
    h.textContent = titulo;
    const fila = document.createElement("div");
    fila.className = "fila";
    fila.innerHTML = items.map(([pie, svg]) => `<figure>${svg}<figcaption>${pie}</figcaption></figure>`).join("");
    s.append(h, fila);
    hoja.appendChild(s);
  };
  const rumbos = [0, 45, 90, 135, 180, 225, 270, 315];
  for (const modelo of ["f16", "su30", "generico"]) {
    seccion(`${modelo} (azul) - rumbos`, rumbos.map((r) => [`${r}°`, Modelo3d.svg({ modelo, rumbo: r, bando: "azul", px: 120 })]));
  }
  seccion("Su-30 rojo y F-16 rojo", [["Su-30 rojo 60°", Modelo3d.svg({ modelo: "su30", rumbo: 60, bando: "rojo", px: 140 })], ["F-16 rojo 240°", Modelo3d.svg({ modelo: "f16", rumbo: 240, bando: "rojo", px: 140 })]]);
  seccion("Formaciones (F-16 x1..4, Su-30 x2)", [1, 2, 3, 4].map((n) => [`F-16 x${n}`, Modelo3d.svg({ modelo: "f16", rumbo: 30, bando: "azul", n, px: 150 })])
    .concat([["Su-30 x2", Modelo3d.svg({ modelo: "su30", rumbo: 30, bando: "azul", n: 2, px: 150 })]]));
  seccion("Tamaño en el mapa (54 px normal / 76 px videowall)", [
    ["F-16 x4", Modelo3d.svg({ modelo: "f16", rumbo: 45, bando: "azul", n: 4, px: 54 })],
    ["Su-30 x2", Modelo3d.svg({ modelo: "su30", rumbo: 45, bando: "azul", n: 2, px: 54 })],
    ["generico", Modelo3d.svg({ modelo: "generico", rumbo: 225, bando: "rojo", n: 1, px: 54 })],
    ["F-16 x4", Modelo3d.svg({ modelo: "f16", rumbo: 45, bando: "azul", n: 4, px: 76 })],
  ]);
})();
