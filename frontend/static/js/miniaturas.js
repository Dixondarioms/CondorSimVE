/* Miniaturas 3D de todas las unidades (aeronaves, buques, vehiculos, personal e instalaciones).
 *
 * Cada miniatura es una malla procedural propia, sin archivos de modelos ni librerias: se arma con las primitivas de
 * js/modelo3d.js (fuselajes, placas, cajas, cilindros, secciones...), se registra para las clases y modelos del
 * catalogo del servidor y el mapa la gira con el rumbo de la unidad. Son formas genericas y estilizadas (del tipo de
 * cada sistema, no de un producto concreto). El color del bando va en las derivas de las aeronaves, en un panel de
 * identificacion o banda de cada vehiculo o buque, y en la peana de todo lo que esta en tierra o en el agua.
 *
 * Ejes: x a estribor, y hacia la proa, z hacia arriba. La escala de cada malla es libre: el dibujo la ajusta a su
 * cuadro, y el tamaño en pantalla lo da `tam` (1 = un caza). */
(function (raiz) {
  "use strict";

  const M = raiz.Modelo3d || (typeof require !== "undefined" ? require("./modelo3d.js") : null);
  const { enCapa, fuselaje, placa, caja, espejo, secciones, cilindro, esfera, disco, transformar } = M.primitivas;

  // ---------------------------------------------------------------- ayudas
  const par = (contorno, espesor, z, tono) => [placa(contorno, espesor, "xy", z, tono), placa(espejo(contorno), espesor, "xy", z, tono)];
  /** Rectangulo de una seccion transversal (para `secciones`). */
  const rect = (x0, x1, z0, z1) => [[x0, z0], [x1, z0], [x1, z1], [x0, z1]];
  const mover = (piezas, t) => transformar(piezas, { t });
  const girarZ = (piezas, grados, pivote = [0, 0, 0]) => transformar(piezas, { rz: grados, pivote });

  /** Ruedas de un vehiculo: `ejes` posiciones en y, a ambos lados en ±x. */
  const ruedas = (ejes, x, r = 0.15, ancho = 0.1) => ejes.flatMap((y) => [
    cilindro("x", [x, y, r], r, ancho, "caucho", 8), cilindro("x", [-x, y, r], r, ancho, "caucho", 8),
  ]);

  /** Orugas: bloques bajos con los extremos redondeados. */
  const orugas = (x0, x1, largo, alto) => [1, -1].map((lado) => secciones([
    [-largo, rect(lado * x0, lado * x1, alto * 0.25, alto * 0.8)],
    [-largo + 0.12, rect(lado * x0, lado * x1, 0, alto)],
    [largo - 0.12, rect(lado * x0, lado * x1, 0, alto)],
    [largo, rect(lado * x0, lado * x1, alto * 0.25, alto * 0.8)],
  ], "oruga"));

  /** Panel de identificacion aerea del color del bando sobre el techo de un vehiculo. */
  const panel = (x, y, z, capa, ancho = 0.2, largo = 0.2) => enCapa(caja([x - ancho / 2, x + ancho / 2], [y - largo / 2, y + largo / 2], [z, z + 0.025], "bando"), capa);

  /** Cabina de camion con parabrisas. */
  function cabinaCamion(y0, y1, ancho, alto, capa = 1) {
    return enCapa([
      caja([-ancho, ancho], [y0, y1], [0.16, alto], "oliva"),
      caja([-ancho * 0.85, ancho * 0.85], [y1 - 0.005, y1 + 0.01], [alto * 0.62, alto * 0.92], "cabina"),
    ], capa);
  }

  // ================================================================ AERONAVES
  function cazaEmbarcado({ growler = false } = {}) {
    const ala = [[0.2, 0.06], [0.82, -0.28], [0.82, -0.42], [0.2, -0.5]];
    const lerx = [[0.06, 0.62], [0.2, 0.12], [0.2, -0.02], [0.08, 0.1]];
    const estab = [[0.14, -0.66], [0.5, -0.82], [0.5, -0.94], [0.14, -0.98]];
    const deriva = [[-0.3, 0.1], [-0.62, 0.52], [-0.78, 0.52], [-0.84, 0.1]];
    return {
      piezas: [
        fuselaje([[1.0, 0.04, 0.04], [0.78, 0.14, 0.13], [0.5, 0.22, 0.19], [0.15, 0.32, 0.22], [-0.4, 0.34, 0.22], [-0.85, 0.3, 0.18], [-1.0, 0.26, 0.16]], "cuerpo"),
        fuselaje([[0.66, 0.05, 0.03, 0.11], [0.48, 0.16, 0.13, 0.13], [0.24, 0.16, 0.1, 0.13], [0.08, 0.05, 0.03, 0.1]], "cabina"),
        caja([0.12, 0.24], [-0.05, 0.3], [-0.16, -0.02], "toma"), caja([-0.24, -0.12], [-0.05, 0.3], [-0.16, -0.02], "toma"),
        ...par(lerx, 0.03, 0.03, "ala"), ...par(ala, 0.035, 0, "ala"), ...par(estab, 0.03, -0.02, "ala"),
        transformar(placa(deriva, 0.035, "yz", 0.13, "deriva"), { ry: 22, pivote: [0.13, 0, 0.1] }),
        transformar(placa(deriva, 0.035, "yz", -0.13, "deriva"), { ry: -22, pivote: [-0.13, 0, 0.1] }),
        // EA-18G: contenedores de escucha en las puntas de ala y de interferencia bajo las alas y el fuselaje
        ...(growler ? [
          cilindro("y", [0.84, -0.32, 0], 0.035, 0.32, "antena", 6), cilindro("y", [-0.84, -0.32, 0], 0.035, 0.32, "antena", 6),
          cilindro("y", [0.5, -0.12, -0.08], 0.05, 0.42, "antena", 6), cilindro("y", [-0.5, -0.12, -0.08], 0.05, 0.42, "antena", 6),
          cilindro("y", [0, 0.1, -0.2], 0.05, 0.4, "antena", 6),
        ] : []),
      ],
    };
  }

  function ataqueLigero() {
    const ala = [[0.1, 0.02], [0.86, -0.12], [0.86, -0.26], [0.1, -0.38]];
    const estab = [[0.06, -0.74], [0.38, -0.82], [0.38, -0.92], [0.06, -0.96]];
    return {
      piezas: [
        fuselaje([[1.0, 0.04, 0.04], [0.8, 0.14, 0.14], [0.5, 0.2, 0.2], [0.1, 0.24, 0.22], [-0.4, 0.2, 0.18], [-0.85, 0.12, 0.12], [-1.0, 0.08, 0.08]], "cuerpo"),
        fuselaje([[0.72, 0.05, 0.03, 0.1], [0.55, 0.15, 0.14, 0.13], [0.1, 0.15, 0.13, 0.14], [-0.08, 0.05, 0.03, 0.11]], "cabina"),
        caja([0.1, 0.2], [-0.1, 0.22], [-0.08, 0.06], "toma"), caja([-0.2, -0.1], [-0.1, 0.22], [-0.08, 0.06], "toma"),
        ...par(ala, 0.035, -0.04, "ala"), ...par(estab, 0.03, 0, "ala"),
        placa([[-0.52, 0.1], [-0.8, 0.48], [-0.94, 0.48], [-0.98, 0.1]], 0.035, "yz", 0, "deriva"),
        // dos bombas bajo las alas
        cilindro("y", [0.45, -0.1, -0.1], 0.04, 0.3, "negro", 6), cilindro("y", [-0.45, -0.1, -0.1], 0.04, 0.3, "negro", 6),
      ],
    };
  }

  /** Rotor principal: disco translucido y palas (en capas superiores al fuselaje). */
  function rotor(c, radio, palas) {
    const piezas = [enCapa(disco(c, radio, "rotor", "xy", 18), 1)];
    for (let k = 0; k < palas; k++) {
      piezas.push(enCapa(girarZ(caja([0, radio], [c[1] - 0.03, c[1] + 0.03], [c[2] + 0.005, c[2] + 0.02], "pala"), 45 + (360 / palas) * k, [0, c[1], 0]), 2));
    }
    piezas.push(enCapa(cilindro("z", [c[0], c[1], c[2] + 0.02], 0.05, 0.04, "negro", 6), 2));
    return piezas;
  }

  function heloAtaque() {
    return {
      piezas: [
        fuselaje([[0.85, 0.08, 0.1, 0.0], [0.7, 0.18, 0.22, 0.02], [0.4, 0.24, 0.3, 0.04], [0.05, 0.26, 0.3, 0.06], [-0.2, 0.18, 0.2, 0.08], [-0.35, 0.09, 0.1, 0.1], [-0.95, 0.06, 0.07, 0.12]], "cuerpo"),
        fuselaje([[0.8, 0.06, 0.04, 0.08], [0.62, 0.15, 0.12, 0.13], [0.3, 0.16, 0.12, 0.17], [0.12, 0.06, 0.04, 0.16]], "cabina"),
        fuselaje([[0.15, 0.1, 0.1, 0.16], [-0.25, 0.12, 0.12, 0.16], [-0.35, 0.08, 0.08, 0.16]], "cuerpo", 0.17),
        fuselaje([[0.15, 0.1, 0.1, 0.16], [-0.25, 0.12, 0.12, 0.16], [-0.35, 0.08, 0.08, 0.16]], "cuerpo", -0.17),
        ...par([[0.12, 0.2], [0.48, 0.16], [0.48, 0.02], [0.12, -0.02]], 0.03, 0.04, "ala"),
        cilindro("y", [0.4, 0.1, -0.02], 0.045, 0.28, "negro", 6), cilindro("y", [-0.4, 0.1, -0.02], 0.045, 0.28, "negro", 6),
        cilindro("z", [0, 0.05, 0.28], 0.035, 0.12, "negro", 6),
        placa([[-0.8, 0.1], [-0.92, 0.42], [-1.0, 0.42], [-0.98, 0.08]], 0.03, "yz", 0, "deriva"),
        ...par([[0.02, -0.86], [0.2, -0.86], [0.2, -0.94], [0.02, -0.94]], 0.02, 0.14, "ala"),
        enCapa(disco([-0.05, -0.95, 0.3], 0.14, "rotor", "yz", 12), 1),
        ...rotor([0, 0.05, 0.34], 0.82, 4),
      ],
    };
  }

  function heloTransporte(armado = true) {
    const cola = [[-0.88, 0.14], [-0.98, 0.46], [-1.06, 0.46], [-1.05, 0.14]];
    return {
      piezas: [
        fuselaje([[0.95, 0.1, 0.14, 0.0], [0.8, 0.26, 0.3, 0.04], [0.55, 0.34, 0.38, 0.06], [0.0, 0.36, 0.4, 0.06], [-0.35, 0.3, 0.34, 0.08], [-0.5, 0.12, 0.14, 0.14], [-1.05, 0.07, 0.08, 0.18]], "cuerpo"),
        fuselaje([[0.92, 0.1, 0.08, 0.1], [0.78, 0.24, 0.14, 0.16], [0.62, 0.26, 0.1, 0.2], [0.55, 0.1, 0.04, 0.2]], "cabina"),
        fuselaje([[0.5, 0.1, 0.08, 0.26], [0.3, 0.26, 0.14, 0.28], [-0.15, 0.26, 0.14, 0.28], [-0.3, 0.12, 0.08, 0.26]], "cuerpo"),
        cilindro("y", [0.22, 0.05, -0.08], 0.07, 0.4, "cuerpo", 7), cilindro("y", [-0.22, 0.05, -0.08], 0.07, 0.4, "cuerpo", 7),
        // afustes con coheteras y la ametralladora
        ...(armado ? [
          ...par([[0.2, 0.12], [0.44, 0.12], [0.44, -0.02], [0.2, -0.02]], 0.025, 0.02, "ala"),
          cilindro("y", [0.42, 0.06, -0.03], 0.045, 0.24, "negro", 6), cilindro("y", [-0.42, 0.06, -0.03], 0.045, 0.24, "negro", 6),
        ] : []),
        placa(cola, 0.03, "yz", 0, "deriva"),
        enCapa(disco([-0.05, -1.0, 0.36], 0.16, "rotor", "yz", 12), 1),
        cilindro("z", [0, 0.12, 0.38], 0.04, 0.1, "negro", 6),
        ...rotor([0, 0.12, 0.42], 0.98, 5),
      ],
    };
  }

  function dronReconocimiento() {
    return {
      piezas: [
        fuselaje([[0.55, 0.04, 0.04, 0.02], [0.4, 0.14, 0.14, 0.02], [0.0, 0.16, 0.16, 0.03], [-0.3, 0.12, 0.12, 0.04], [-0.42, 0.06, 0.06, 0.05]], "cuerpo"),
        esfera([0, 0.3, -0.08], 0.06, "negro"),
        placa([[-1.0, 0.12], [1.0, 0.12], [1.0, -0.04], [-1.0, -0.04]], 0.025, "xy", 0.1, "ala"),
        cilindro("y", [0.3, -0.45, 0.09], 0.025, 0.9, "cuerpo", 6), cilindro("y", [-0.3, -0.45, 0.09], 0.025, 0.9, "cuerpo", 6),
        placa([[-0.34, -0.82], [0.34, -0.82], [0.34, -0.9], [-0.34, -0.9]], 0.02, "xy", 0.18, "ala"),
        placa([[-0.8, 0.08], [-0.84, 0.24], [-0.9, 0.24], [-0.9, 0.08]], 0.02, "yz", 0.3, "deriva"),
        placa([[-0.8, 0.08], [-0.84, 0.24], [-0.9, 0.24], [-0.9, 0.08]], 0.02, "yz", -0.3, "deriva"),
        enCapa(disco([0, -0.45, 0.05], 0.14, "rotor", "xz", 12), 1),
      ],
    };
  }

  function dronArmado() {
    const ala = [[-1.1, 0.06], [-0.1, 0.16], [0.1, 0.16], [1.1, 0.06], [1.1, -0.02], [0.1, -0.06], [-0.1, -0.06], [-1.1, -0.02]];
    const cola = [[-0.52, 0.05], [-0.66, 0.3], [-0.74, 0.3], [-0.7, 0.05]];
    return {
      piezas: [
        fuselaje([[0.8, 0.06, 0.08, 0.02], [0.65, 0.2, 0.22, 0.04], [0.35, 0.22, 0.22, 0.02], [-0.2, 0.2, 0.18, 0.02], [-0.6, 0.12, 0.1, 0.02], [-0.75, 0.06, 0.06, 0.02]], "cuerpo"),
        esfera([0, 0.55, 0.1], 0.12, "cuerpo", 8, 0.8),
        esfera([0, 0.62, -0.1], 0.06, "negro"),
        placa(ala, 0.025, "xy", 0.02, "ala"),
        transformar(placa(cola, 0.02, "yz", 0, "deriva"), { ry: 45, pivote: [0, -0.6, 0.05] }),
        transformar(placa(cola, 0.02, "yz", 0, "deriva"), { ry: -45, pivote: [0, -0.6, 0.05] }),
        placa([[-0.55, -0.02], [-0.68, -0.2], [-0.74, -0.2], [-0.72, -0.02]], 0.02, "yz", 0, "deriva"),
        ...[0.45, 0.62, -0.45, -0.62].map((x) => cilindro("y", [x, 0.08, -0.05], 0.022, 0.3, "misil", 6)),
        enCapa(disco([0, -0.78, 0.02], 0.18, "rotor", "xz", 12), 1),
      ],
    };
  }

  function merodeadora() {
    return {
      piezas: [
        placa([[0, 0.55], [0.62, -0.35], [0.62, -0.5], [-0.62, -0.5], [-0.62, -0.35]], 0.03, "xy", 0, "ala"),
        fuselaje([[0.62, 0.03, 0.03], [0.45, 0.12, 0.1], [0.0, 0.14, 0.12], [-0.5, 0.1, 0.1]], "cuerpo"),
        placa([[-0.3, -0.06], [-0.4, 0.18], [-0.5, 0.18], [-0.5, -0.06]], 0.02, "yz", 0.62, "deriva"),
        placa([[-0.3, -0.06], [-0.4, 0.18], [-0.5, 0.18], [-0.5, -0.06]], 0.02, "yz", -0.62, "deriva"),
        enCapa(disco([0, -0.52, 0], 0.12, "rotor", "xz", 12), 1),
      ],
    };
  }

  function avionGe() {
    const ala = [[0.08, 0.1], [0.95, -0.3], [0.95, -0.38], [0.08, -0.2]];
    const motor = (x) => fuselaje([[-0.4, 0.1, 0.1, 0.1], [-0.5, 0.12, 0.12, 0.1], [-0.72, 0.11, 0.11, 0.1], [-0.8, 0.08, 0.08, 0.1]], "cuerpo", x);
    return {
      piezas: [
        fuselaje([[1.0, 0.04, 0.05, 0.02], [0.85, 0.14, 0.15, 0.03], [0.6, 0.2, 0.2, 0.04], [-0.4, 0.2, 0.2, 0.04], [-0.8, 0.12, 0.14, 0.07], [-0.95, 0.06, 0.08, 0.09]], "cuerpo"),
        fuselaje([[0.86, 0.1, 0.06, 0.08], [0.75, 0.16, 0.1, 0.1], [0.68, 0.14, 0.06, 0.11]], "cabina"),
        ...par(ala, 0.03, -0.04, "ala"),
        motor(0.19), motor(-0.19),
        placa([[-0.68, 0.08], [-0.9, 0.42], [-1.0, 0.42], [-0.98, 0.08]], 0.03, "yz", 0, "deriva"),
        ...par([[0.0, -0.88], [0.34, -0.98], [0.34, -1.04], [0.0, -1.02]], 0.02, 0.42, "ala"),
        // canoa ventral de las antenas de interferencia y cuchillas de escucha en el lomo
        fuselaje([[0.45, 0.04, 0.03, -0.1], [0.3, 0.12, 0.1, -0.12], [-0.3, 0.12, 0.1, -0.12], [-0.45, 0.04, 0.03, -0.1]], "antena"),
        ...[0.4, 0.15, -0.1].map((y) => placa([[y, 0.12], [y - 0.04, 0.2], [y - 0.1, 0.2], [y - 0.1, 0.12]], 0.015, "yz", 0, "negro")),
      ],
    };
  }

  function misilCrucero() {
    const aleta = placa([[-0.74, 0.1], [-0.88, 0.3], [-0.97, 0.3], [-0.96, 0.1]], 0.02, "yz", 0, "deriva");
    return {
      piezas: [
        fuselaje([[1.0, 0.02, 0.02], [0.9, 0.1, 0.1], [0.75, 0.14, 0.14], [-0.85, 0.14, 0.14], [-0.97, 0.1, 0.1]], "misil"),
        ...par([[0.05, 0.12], [0.62, 0.04], [0.62, -0.03], [0.05, -0.06]], 0.02, 0.0, "misil"),
        ...[45, 135, 225, 315].map((g) => transformar(aleta, { ry: g, pivote: [0, 0, 0] })),
        caja([-0.05, 0.05], [-0.55, -0.3], [-0.12, -0.06], "negro"),
      ],
    };
  }

  // ---------------------------------------------------------------- aeronaves de EE. UU. (plantilla del 3 de enero)
  /** Caza furtivo de ala en diamante y derivas inclinadas (F-22). */
  function f22() {
    const ala = [[0.18, 0.25], [0.86, -0.38], [0.86, -0.5], [0.18, -0.62]];
    const estab = [[0.16, -0.68], [0.5, -0.8], [0.5, -0.95], [0.16, -1.0]];
    const deriva = [[-0.42, 0.08], [-0.66, 0.42], [-0.8, 0.42], [-0.86, 0.08]];
    return {
      piezas: [
        fuselaje([[1.0, 0.03, 0.03], [0.8, 0.14, 0.1], [0.5, 0.26, 0.14], [0.1, 0.42, 0.15], [-0.5, 0.42, 0.14], [-0.9, 0.32, 0.1], [-1.0, 0.28, 0.08]], "cuerpo"),
        fuselaje([[0.74, 0.05, 0.03, 0.07], [0.58, 0.14, 0.1, 0.1], [0.32, 0.14, 0.08, 0.1], [0.18, 0.05, 0.03, 0.08]], "cabina"),
        caja([0.14, 0.26], [0.0, 0.34], [-0.1, 0.02], "toma"), caja([-0.26, -0.14], [0.0, 0.34], [-0.1, 0.02], "toma"),
        ...par(ala, 0.03, 0, "ala"), ...par(estab, 0.025, -0.01, "ala"),
        transformar(placa(deriva, 0.03, "yz", 0.2, "deriva"), { ry: 28, pivote: [0.2, 0, 0.08] }),
        transformar(placa(deriva, 0.03, "yz", -0.2, "deriva"), { ry: -28, pivote: [-0.2, 0, 0.08] }),
      ],
    };
  }

  /** Caza furtivo monomotor (F-35A; `stovl`: F-35B, con las puertas del ventilador de sustentacion). */
  function f35(stovl = false) {
    const ala = [[0.18, 0.12], [0.76, -0.34], [0.76, -0.46], [0.18, -0.56]];
    const estab = [[0.14, -0.66], [0.46, -0.76], [0.46, -0.9], [0.14, -0.96]];
    const deriva = [[-0.5, 0.08], [-0.7, 0.36], [-0.82, 0.36], [-0.86, 0.08]];
    return {
      piezas: [
        fuselaje([[1.0, 0.03, 0.04], [0.8, 0.16, 0.13], [0.45, 0.3, 0.18], [0.05, 0.4, 0.2], [-0.5, 0.36, 0.18], [-0.85, 0.2, 0.14], [-1.0, 0.14, 0.12]], "cuerpo"),
        fuselaje([[0.72, 0.05, 0.03, 0.09], [0.56, 0.15, 0.11, 0.12], [0.3, 0.15, 0.09, 0.12], [0.16, 0.05, 0.03, 0.1]], "cabina"),
        caja([0.15, 0.26], [0.05, 0.36], [-0.12, 0.02], "toma"), caja([-0.26, -0.15], [0.05, 0.36], [-0.12, 0.02], "toma"),
        ...par(ala, 0.03, -0.01, "ala"), ...par(estab, 0.025, -0.02, "ala"),
        transformar(placa(deriva, 0.03, "yz", 0.15, "deriva"), { ry: 25, pivote: [0.15, 0, 0.08] }),
        transformar(placa(deriva, 0.03, "yz", -0.15, "deriva"), { ry: -25, pivote: [-0.15, 0, 0.08] }),
        ...(stovl ? [enCapa(caja([-0.1, 0.1], [0.02, 0.2], [0.19, 0.21], "negro"), 1), enCapa(caja([-0.06, 0.06], [-0.3, -0.18], [0.17, 0.19], "negro"), 1)] : []),
      ],
    };
  }

  /** Bombardero de ala en flecha variable con cuatro motores en dos gondolas (B-1B). */
  function b1b() {
    const gondola = [[-0.05, 0.12, 0.1, -0.08], [-0.15, 0.16, 0.12, -0.09], [-0.6, 0.16, 0.12, -0.09], [-0.68, 0.12, 0.1, -0.08]];
    return {
      piezas: [
        fuselaje([[1.0, 0.02, 0.03, 0.0], [0.82, 0.1, 0.1, 0.02], [0.5, 0.16, 0.14, 0.03], [0.1, 0.28, 0.12, 0.03], [-0.4, 0.28, 0.12, 0.03], [-0.8, 0.14, 0.1, 0.04], [-1.0, 0.06, 0.06, 0.05]], "cuerpo"),
        fuselaje([[0.82, 0.04, 0.02, 0.06], [0.72, 0.1, 0.06, 0.08], [0.6, 0.08, 0.04, 0.08]], "cabina"),
        ...par([[0.0, 0.42], [0.3, 0.06], [0.3, -0.16], [0.0, -0.22]], 0.04, 0.02, "ala"),
        ...par([[0.28, 0.04], [1.0, -0.5], [1.0, -0.58], [0.28, -0.12]], 0.03, 0.02, "ala"),
        fuselaje(gondola, "cuerpo", 0.2), fuselaje(gondola, "cuerpo", -0.2),
        placa([[-0.6, 0.06], [-0.88, 0.42], [-1.0, 0.42], [-1.0, 0.06]], 0.03, "yz", 0, "deriva"),
        ...par([[0.02, -0.8], [0.36, -0.92], [0.36, -0.98], [0.02, -0.97]], 0.025, 0.22, "ala"),
      ],
    };
  }

  /** Reactor de cuatro (o dos) motores de ala baja en flecha: base de E-3, RC-135, KC-135 y P-8. */
  function reactorPesado({ motores = 4, rotodomo = false, mejillas = false, pertiga = false } = {}) {
    const ala = [[0.1, 0.12], [1.0, -0.42], [1.0, -0.5], [0.1, -0.2]];
    const motor = (x) => {
      const y = 0.12 - 0.6 * (Math.abs(x) - 0.1) + 0.1; // delante del borde de ataque, que va en flecha
      return fuselaje([[y + 0.06, 0.06, 0.06, -0.06], [y, 0.08, 0.08, -0.06], [y - 0.2, 0.07, 0.07, -0.06], [y - 0.24, 0.05, 0.05, -0.06]], "cuerpo", x);
    };
    const xs = motores === 4 ? [0.36, 0.66] : [0.34];
    const mejilla = [[0.78, 0.03, 0.04, 0.0], [0.7, 0.05, 0.09, 0.0], [0.4, 0.05, 0.09, 0.0], [0.34, 0.03, 0.04, 0.0]];
    return {
      piezas: [
        fuselaje([[1.0, 0.03, 0.04, 0.02], [0.92, 0.1, 0.11, 0.02], [0.8, 0.13, 0.14, 0.02], [-0.6, 0.13, 0.14, 0.02], [-0.88, 0.08, 0.1, 0.06], [-1.0, 0.03, 0.05, 0.09]], "cuerpo"),
        fuselaje([[0.93, 0.08, 0.03, 0.06], [0.86, 0.11, 0.04, 0.07]], "cabina"),
        ...par(ala, 0.03, -0.03, "ala"),
        ...xs.flatMap((x) => [motor(x), motor(-x)]),
        placa([[-0.62, 0.1], [-0.9, 0.44], [-1.0, 0.44], [-0.98, 0.08]], 0.03, "yz", 0, "deriva"),
        ...par([[0.04, -0.78], [0.36, -0.92], [0.36, -0.98], [0.04, -0.96]], 0.025, 0.06, "ala"),
        ...(rotodomo ? [
          caja([-0.03, 0.03], [-0.42, -0.3], [0.08, 0.28], "cuerpo"),
          enCapa(cilindro("z", [0, -0.36, 0.3], 0.3, 0.06, "radomo", 16), 2),
          enCapa(cilindro("z", [0, -0.36, 0.335], 0.08, 0.01, "negro", 8), 3),
        ] : []),
        ...(mejillas ? [fuselaje(mejilla, "antena", 0.13), fuselaje(mejilla, "antena", -0.13), esfera([0, 1.0, 0.02], 0.05, "radomo")] : []),
        ...(pertiga ? [transformar(caja([-0.015, 0.015], [-1.3, -0.96], [-0.02, 0.01], "negro"), { rx: 22, pivote: [0, -0.96, 0] })] : []),
      ],
    };
  }

  /** Cuatrimotor turbohelice de ala alta (C-130); `ge`: EC-130H, con antenas entre la deriva y el estabilizador. */
  function c130(ge = false) {
    const motor = (x) => [
      fuselaje([[0.42, 0.05, 0.06, 0.12], [0.36, 0.08, 0.09, 0.12], [0.1, 0.08, 0.09, 0.12], [0.0, 0.05, 0.06, 0.12]], "cuerpo", x),
      enCapa(disco([x, 0.45, 0.12], 0.15, "rotor", "xz", 12), 1),
    ];
    return {
      piezas: [
        fuselaje([[1.0, 0.06, 0.08, 0.0], [0.9, 0.16, 0.18, 0.02], [0.75, 0.2, 0.22, 0.03], [-0.35, 0.2, 0.22, 0.03], [-0.7, 0.1, 0.12, 0.12], [-0.95, 0.05, 0.06, 0.17]], "cuerpo"),
        fuselaje([[0.92, 0.12, 0.05, 0.1], [0.84, 0.16, 0.06, 0.12]], "cabina"),
        ...par([[0.05, 0.28], [1.0, 0.22], [1.0, 0.1], [0.05, 0.06]], 0.03, 0.14, "ala"),
        ...[0.32, 0.62].flatMap((x) => [...motor(x), ...motor(-x)]),
        placa([[-0.6, 0.15], [-0.85, 0.6], [-0.98, 0.6], [-0.98, 0.12]], 0.03, "yz", 0, "deriva"),
        ...par([[0.03, -0.82], [0.42, -0.86], [0.42, -0.96], [0.03, -0.98]], 0.025, 0.17, "ala"),
        ...(ge ? [
          caja([-0.006, 0.006], [-0.95, -0.6], [0.2, 0.58], "antena"),
          caja([0.36, 0.38], [-0.9, -0.85], [0.17, 0.42], "antena"), caja([-0.38, -0.36], [-0.9, -0.85], [0.17, 0.42], "antena"),
          cilindro("y", [0.82, 0.12, 0.08], 0.035, 0.3, "antena", 6), cilindro("y", [-0.82, 0.12, 0.08], 0.035, 0.3, "antena", 6),
        ] : []),
      ],
    };
  }

  /** Alerta temprana embarcada: biturbohelice de ala alta con domo giratorio y cuatro derivas (E-2D). */
  function e2d() {
    const motor = (x) => [
      fuselaje([[0.42, 0.06, 0.07, 0.1], [0.34, 0.09, 0.1, 0.1], [-0.05, 0.08, 0.09, 0.1], [-0.15, 0.05, 0.05, 0.1]], "cuerpo", x),
      enCapa(disco([x, 0.45, 0.1], 0.22, "rotor", "xz", 12), 1),
    ];
    const deriva = [[-0.76, 0.1], [-0.8, 0.4], [-0.9, 0.4], [-0.94, 0.1]];
    return {
      piezas: [
        fuselaje([[1.0, 0.05, 0.07, 0.0], [0.88, 0.15, 0.18, 0.02], [0.7, 0.2, 0.22, 0.03], [-0.4, 0.18, 0.2, 0.05], [-0.75, 0.1, 0.1, 0.1], [-0.88, 0.06, 0.06, 0.12]], "cuerpo"),
        fuselaje([[0.92, 0.1, 0.05, 0.08], [0.82, 0.15, 0.06, 0.1]], "cabina"),
        ...par([[0.05, 0.2], [1.0, 0.14], [1.0, 0.02], [0.05, -0.02]], 0.03, 0.12, "ala"),
        ...motor(0.3), ...motor(-0.3),
        caja([-0.03, 0.03], [-0.2, 0.0], [0.12, 0.34], "cuerpo"),
        enCapa(cilindro("z", [0, -0.1, 0.38], 0.42, 0.07, "radomo", 18), 2),
        enCapa(cilindro("z", [0, -0.1, 0.42], 0.1, 0.01, "negro", 8), 3),
        ...par([[0.02, -0.78], [0.44, -0.8], [0.44, -0.92], [0.02, -0.94]], 0.025, 0.12, "ala"),
        ...[0.44, 0.18, -0.18, -0.44].map((x) => placa(deriva, 0.025, "yz", x, "deriva")),
      ],
    };
  }

  /** Dron furtivo de ala volante (RQ-170): sin derivas, lleva el color del bando en un panel del lomo. */
  function rq170() {
    return {
      piezas: [
        fuselaje([[0.45, 0.05, 0.03, 0.0], [0.3, 0.3, 0.1, 0.02], [0.0, 0.42, 0.11, 0.02], [-0.25, 0.3, 0.06, 0.02], [-0.35, 0.15, 0.04, 0.02]], "cuerpo"),
        ...par([[0.15, 0.25], [1.0, -0.35], [1.0, -0.45], [0.15, -0.16]], 0.03, 0.0, "ala"),
        enCapa(caja([-0.08, 0.08], [-0.12, 0.05], [0.07, 0.085], "bando"), 1),
      ],
    };
  }

  /** Helicoptero pesado de rotores en tandem (MH-47G), con tanques laterales y pertiga de reabastecimiento. */
  function chinook() {
    return {
      piezas: [
        fuselaje([[1.0, 0.06, 0.12, 0.04], [0.9, 0.22, 0.3, 0.08], [0.75, 0.28, 0.34, 0.1], [-0.75, 0.28, 0.34, 0.1], [-0.9, 0.22, 0.3, 0.12], [-1.0, 0.12, 0.2, 0.16]], "cuerpo"),
        fuselaje([[0.98, 0.08, 0.06, 0.12], [0.88, 0.22, 0.12, 0.16], [0.8, 0.22, 0.08, 0.18]], "cabina"),
        cilindro("y", [0.2, 0.05, -0.02], 0.08, 0.9, "cuerpo", 8), cilindro("y", [-0.2, 0.05, -0.02], 0.08, 0.9, "cuerpo", 8),
        caja([-0.1, 0.1], [-1.0, -0.62], [0.22, 0.46], "deriva"),
        caja([-0.08, 0.08], [0.72, 0.95], [0.22, 0.3], "cuerpo"),
        cilindro("y", [0.15, 1.12, 0.02], 0.015, 0.36, "negro", 6),
        ...rotor([0, 0.82, 0.34], 0.85, 3), ...transformar(rotor([0, -0.8, 0.5], 0.85, 3), { rz: 60, pivote: [0, -0.8, 0] }),
      ],
    };
  }

  /** Helicoptero ligero (Little Bird): `tipo` "ah" con coheteras, "mh" con bancos exteriores para la tropa. */
  function littleBird(tipo = "ah") {
    const armas = tipo === "ah"
      ? [...par([[0.14, 0.12], [0.36, 0.12], [0.36, 0.0], [0.14, 0.0]], 0.02, 0.0, "ala"),
        cilindro("y", [0.36, 0.06, -0.04], 0.05, 0.3, "negro", 6), cilindro("y", [-0.36, 0.06, -0.04], 0.05, 0.3, "negro", 6)]
      : [caja([0.16, 0.36], [-0.15, 0.3], [-0.04, -0.01], "metal"), caja([-0.36, -0.16], [-0.15, 0.3], [-0.04, -0.01], "metal")];
    return {
      piezas: [
        fuselaje([[0.55, 0.06, 0.1, 0.0], [0.45, 0.2, 0.26, 0.02], [0.2, 0.28, 0.32, 0.04], [-0.1, 0.26, 0.3, 0.06], [-0.25, 0.12, 0.14, 0.1], [-0.3, 0.06, 0.07, 0.12]], "cuerpo"),
        fuselaje([[0.55, 0.08, 0.1, 0.06], [0.42, 0.22, 0.18, 0.1], [0.25, 0.24, 0.14, 0.13]], "cabina"),
        fuselaje([[-0.28, 0.06, 0.07, 0.12], [-1.0, 0.03, 0.04, 0.14]], "cuerpo"),
        placa([[-0.86, 0.1], [-0.92, 0.34], [-1.0, 0.34], [-1.0, 0.06]], 0.025, "yz", 0, "deriva"),
        ...par([[0.0, -0.84], [0.16, -0.84], [0.16, -0.92], [0.0, -0.92]], 0.02, 0.13, "ala"),
        ...armas,
        ...rotor([0, 0.05, 0.34], 0.8, 5),
      ],
    };
  }

  // ================================================================ PERSONAL
  /** Soldado de pie (o rodilla en tierra) mirando a +y; `arma`: "fusil", "tubo" (misil portatil) o nada. */
  function soldado(x, y, { rodilla = false, arma = "fusil" } = {}) {
    const alto = rodilla ? 0.62 : 0.84;
    const piezas = [
      rodilla ? caja([-0.1, 0.1], [-0.12, 0.12], [0, 0.26], "uniforme") : caja([-0.09, 0.09], [-0.05, 0.05], [0, 0.42], "uniforme"),
      caja([-0.13, 0.13], [-0.08, 0.08], [alto - 0.44, alto - 0.12], "uniforme"),
      esfera([0, 0, alto - 0.04], 0.08, "piel", 7),
      esfera([0, -0.005, alto + 0.005], 0.1, "oliva2", 8, 0.62),
    ];
    if (arma === "fusil") piezas.push(caja([0.1, 0.14], [-0.02, 0.36], [alto - 0.22, alto - 0.17], "negro"));
    if (arma === "tubo") piezas.push(transformar(cilindro("y", [0.13, 0.05, alto - 0.08], 0.05, 0.78, "oliva2", 7), { rx: 28, pivote: [0.13, 0.05, alto - 0.08] }));
    return mover(piezas, [x, y, 0]);
  }

  const infanteria = () => ({ piezas: [soldado(0, 0.4), soldado(-0.45, -0.2), soldado(0.45, -0.2)].flat() });
  const antiaereaPortatil = () => ({ piezas: [soldado(0.12, 0.15, { arma: "tubo" }), soldado(-0.34, -0.25, { rodilla: true })].flat() });

  // ================================================================ VEHICULOS
  function tanque() {
    const torre = [[-0.42, 0.45], [0.42, 0.45], [0.46, 0.6], [0.36, 0.72], [-0.36, 0.72], [-0.46, 0.6]];
    const esc = (pts, k) => pts.map(([x, z]) => [x * k, 0.45 + (z - 0.45) * (k > 0.8 ? 1 : 0.85)]);
    return {
      piezas: [
        ...orugas(0.46, 0.66, 1.0, 0.34),
        secciones([[-1.0, rect(-0.52, 0.52, 0.12, 0.45)], [0.72, rect(-0.52, 0.52, 0.12, 0.45)], [1.02, rect(-0.52, 0.52, 0.16, 0.3)]], "oliva"),
        enCapa(secciones([[-0.62, torre], [0.2, torre], [0.5, esc(torre, 0.72)]], "oliva"), 1),
        enCapa(cilindro("y", [0, 1.08, 0.6], 0.04, 1.2, "oliva2", 6), 2),
        enCapa(cilindro("z", [0.2, -0.2, 0.76], 0.09, 0.08, "oliva2", 7), 2),
        panel(-0.12, -0.42, 0.72, 2, 0.26, 0.2),
      ],
    };
  }

  function artilleria() {
    return {
      piezas: [
        ...orugas(0.46, 0.64, 1.0, 0.32),
        secciones([[-1.0, rect(-0.5, 0.5, 0.12, 0.42)], [0.75, rect(-0.5, 0.5, 0.12, 0.42)], [1.02, rect(-0.5, 0.5, 0.16, 0.3)]], "oliva"),
        enCapa(caja([-0.46, 0.46], [-0.98, 0.25], [0.42, 0.86], "oliva"), 1),
        enCapa(transformar([
          cilindro("y", [0, 0.95, 0.66], 0.055, 1.5, "oliva2", 6),
          caja([-0.08, 0.08], [1.66, 1.8], [0.6, 0.72], "oliva2"),
        ], { rx: 18, pivote: [0, 0.25, 0.66] }), 2),
        panel(0, -0.55, 0.86, 2, 0.3, 0.3),
      ],
    };
  }

  function reconocimiento() {
    const casco = (k) => [[-0.4 * k, 0.16], [0.4 * k, 0.16], [0.48 * k, 0.32], [0.4 * k, 0.56], [-0.4 * k, 0.56], [-0.48 * k, 0.32]];
    return {
      piezas: [
        ...ruedas([-0.72, -0.26, 0.26, 0.72], 0.45, 0.16, 0.1),
        secciones([[-1.0, casco(1)], [0.62, casco(1)], [1.0, casco(0.72).map(([x, z]) => [x, z * 0.85 + 0.03])]], "oliva"),
        enCapa(secciones([[-0.3, rect(-0.26, 0.26, 0.56, 0.76)], [0.2, rect(-0.26, 0.26, 0.56, 0.76)], [0.32, rect(-0.2, 0.2, 0.56, 0.7)]], "oliva"), 1),
        enCapa(cilindro("y", [0, 0.7, 0.68], 0.025, 0.8, "negro", 6), 2),
        panel(0, -0.7, 0.56, 1, 0.26, 0.2),
      ],
    };
  }

  /** Chasis de camion (plataforma, cabina adelante y ruedas). */
  function camion({ largo = 1.0, ancho = 0.34, ejes = [-0.7, -0.3, 0.55], cabina = 0.62 } = {}) {
    return [
      ...ruedas(ejes, ancho + 0.02, 0.14, 0.09),
      caja([-ancho, ancho], [-largo, largo], [0.12, 0.24], "oliva2"),
      ...cabinaCamion(largo - 0.4, largo, ancho, cabina),
    ];
  }

  function antiaerea() {
    const contenedor = (x, z) => caja([x - 0.15, x + 0.15], [-0.8, 0.45], [z, z + 0.24], "oliva");
    return {
      piezas: [
        ...camion({ largo: 1.0, ancho: 0.4, ejes: [-0.72, -0.35, 0.6] }),
        enCapa(caja([-0.3, 0.3], [-0.9, -0.5], [0.24, 0.42], "oliva2"), 1),
        enCapa(transformar([contenedor(-0.16, 0.42), contenedor(0.16, 0.42), contenedor(-0.16, 0.67), contenedor(0.16, 0.67)],
          { rx: 38, pivote: [0, -0.7, 0.42] }), 2),
        panel(0, 0.8, 0.62, 2, 0.26, 0.2),
      ],
    };
  }

  function ingenieros() {
    return {
      piezas: [
        ...orugas(0.44, 0.62, 0.95, 0.32),
        secciones([[-0.95, rect(-0.48, 0.48, 0.12, 0.44)], [0.8, rect(-0.48, 0.48, 0.12, 0.44)], [0.98, rect(-0.48, 0.48, 0.14, 0.32)]], "oliva"),
        enCapa(caja([-0.36, 0.2], [-0.5, 0.4], [0.44, 0.78], "oliva"), 1),
        enCapa(caja([-0.3, 0.14], [0.39, 0.41], [0.56, 0.72], "cabina"), 2),
        // pala de empuje adelante y pluma de la grua
        placa([[-0.7, 0.02], [0.7, 0.02], [0.72, 0.42], [-0.72, 0.42]], 0.06, "xz", 1.14, "metal"),
        caja([-0.3, -0.26], [0.95, 1.14], [0.2, 0.26], "metal"), caja([0.26, 0.3], [0.95, 1.14], [0.2, 0.26], "metal"),
        enCapa(transformar(caja([0.3, 0.38], [-0.9, 0.5], [0.46, 0.54], "grua"), { rx: 22, pivote: [0.34, -0.9, 0.46] }), 2),
        panel(-0.1, -0.2, 0.78, 2, 0.24, 0.2),
      ],
    };
  }

  function convoy() {
    const arco = [[-0.34, 0.24], [0.34, 0.24], [0.34, 0.58], [0.22, 0.7], [-0.22, 0.7], [-0.34, 0.58]];
    const unCamion = [
      ...camion({ largo: 0.95, ancho: 0.34, ejes: [-0.65, -0.3, 0.55] }),
      enCapa(secciones([[-0.95, arco], [0.5, arco]], "lona"), 1),
      panel(0, 0.75, 0.62, 2, 0.22, 0.16),
    ];
    return { piezas: [...mover(unCamion, [0, 1.05, 0]), ...mover(unCamion, [0, -1.05, 0])] };
  }

  function radar() {
    const arreglo = transformar(placa([[-0.72, 0.0], [0.72, 0.0], [0.72, 0.78], [-0.72, 0.78]], 0.07, "xz", 0, "antena"),
      { rx: -16, pivote: [0, 0, 0] });
    return {
      piezas: [
        ...camion({ largo: 1.0, ancho: 0.38, ejes: [-0.72, -0.35, 0.6] }),
        enCapa(caja([-0.3, 0.3], [-0.95, -0.5], [0.24, 0.5], "oliva"), 1),
        enCapa(cilindro("z", [0, -0.05, 0.42], 0.12, 0.36, "metal", 8), 1),
        enCapa(mover(arreglo, [0, -0.05, 0.62]), 2),
        enCapa(mover(transformar(placa([[-0.6, 0.06], [0.6, 0.06], [0.6, 0.12], [-0.6, 0.12]], 0.075, "xz", 0, "negro"), { rx: -16 }), [0, -0.05, 0.62]), 3),
        panel(0, 0.8, 0.62, 2, 0.26, 0.2),
      ],
    };
  }

  function guerraElectronica() {
    return {
      piezas: [
        ...camion({ largo: 1.0, ancho: 0.38, ejes: [-0.72, -0.35, 0.6] }),
        enCapa(caja([-0.38, 0.38], [-1.0, 0.5], [0.24, 0.74], "oliva"), 1),
        enCapa([
          cilindro("z", [0.22, -0.8, 1.05], 0.025, 0.62, "metal", 6), cilindro("z", [-0.22, -0.2, 1.1], 0.025, 0.72, "metal", 6),
          placa([[-0.14, 1.3], [0.14, 1.3], [0.14, 1.36], [-0.14, 1.36]], 0.02, "xz", -0.8, "negro"),
          placa([[-0.1, 1.42], [0.1, 1.42], [0.1, 1.5], [-0.1, 1.5]], 0.02, "xz", -0.2, "negro"),
          transformar(esfera([0, 0.2, 0.86], 0.2, "antena", 10, 0.35), { rx: 55, pivote: [0, 0.2, 0.86] }),
        ], 2),
        panel(0, 0.8, 0.62, 2, 0.26, 0.2),
      ],
    };
  }

  function lanzadorMisiles() {
    const tubo = (x) => cilindro("y", [x, -0.1, 0.5], 0.2, 2.0, "oliva", 10);
    return {
      piezas: [
        ...camion({ largo: 1.25, ancho: 0.44, ejes: [-1.0, -0.62, 0.45, 0.82], cabina: 0.66 }),
        enCapa(transformar([tubo(0.22), tubo(-0.22)], { rx: 14, pivote: [0, -1.1, 0.46] }), 1),
        panel(0, 1.05, 0.66, 2, 0.28, 0.2),
      ],
    };
  }

  // ================================================================ BUQUES
  /** Casco: secciones desde la popa (y = -1) a la proa (y = 1) con la cubierta plana a `franco`. */
  function casco({ manga = 0.26, franco = 0.1, popa = 0.8, afinado = 0.25, tono = "casco" } = {}) {
    const w = manga / 2;
    const sec = (y, a) => [y, [[-a * 0.78, 0], [a * 0.78, 0], [a, franco], [-a, franco]]];
    return secciones([sec(-1, w * popa), sec(-0.5, w), sec(afinado, w), sec(0.72, w * 0.62), sec(1, w * 0.05)], tono);
  }

  /** Cubierta (contorno del casco) apenas encima del casco, en la capa 1. */
  function cubierta({ manga = 0.26, franco = 0.1, popa = 0.8, afinado = 0.25, tono = "cubierta" } = {}) {
    const w = manga / 2 - 0.004;
    const lado = [[w * popa, -0.995], [w, -0.5], [w, afinado], [w * 0.62, 0.72], [w * 0.05, 0.995]];
    const contorno = [...lado, ...lado.slice().reverse().map(([x, y]) => [-x, y])];
    return enCapa(placa(contorno, 0.004, "xy", franco + 0.002, tono), 1);
  }

  /** Circulo blanco de la cubierta de vuelo de un helicoptero. */
  const helipuerto = (y, z, r = 0.07) => [enCapa(disco([0, y, z], r, "linea", "xy", 16), 2), enCapa(disco([0, y, z + 0.003], r * 0.78, "cubierta", "xy", 16), 3)];

  /** Cañon naval: torreta y tubo hacia proa. */
  const canon = (y, z, k = 1) => [
    enCapa(fuselaje([[y + 0.07 * k, 0.05 * k, 0.03 * k, z + 0.04 * k], [y, 0.1 * k, 0.08 * k, z + 0.04 * k], [y - 0.06 * k, 0.09 * k, 0.07 * k, z + 0.04 * k]], "superestructura"), 3),
    enCapa(cilindro("y", [0, y + 0.18 * k, z + 0.045 * k], 0.01 * k, 0.22 * k, "metal", 5), 4),
  ];

  /** Mastil con verga y antena de radar. */
  const mastil = (y, z0, alto, capa = 4) => enCapa([
    cilindro("z", [0, y, z0 + alto / 2], 0.012, alto, "metal", 5),
    caja([-0.07, 0.07], [y - 0.006, y + 0.006], [z0 + alto * 0.72, z0 + alto * 0.72 + 0.012], "metal"),
    placa([[-0.05, z0 + alto * 0.86], [0.05, z0 + alto * 0.86], [0.05, z0 + alto * 0.94], [-0.05, z0 + alto * 0.94]], 0.012, "xz", y, "antena"),
  ], capa);

  /** Chimenea con la banda del color del bando. */
  const chimenea = (y, z0, alto = 0.12, ancho = 0.05) => [
    enCapa(caja([-ancho, ancho], [y - 0.06, y + 0.06], [z0, z0 + alto], "superestructura"), 3),
    enCapa(caja([-ancho - 0.003, ancho + 0.003], [y - 0.063, y + 0.063], [z0 + alto * 0.55, z0 + alto * 0.8], "bando"), 4),
    enCapa(caja([-ancho, ancho], [y - 0.06, y + 0.06], [z0 + alto, z0 + alto + 0.012], "negro"), 4),
  ];

  function patrullero() {
    const c = { manga: 0.32, franco: 0.11, popa: 0.85, afinado: 0.1 };
    return {
      piezas: [
        casco(c), cubierta(c),
        enCapa(caja([-0.11, 0.11], [-0.2, 0.32], [0.11, 0.24], "superestructura"), 2),
        enCapa(caja([-0.1, 0.1], [0.12, 0.3], [0.24, 0.32], "superestructura"), 3),
        enCapa(caja([-0.095, 0.095], [0.295, 0.305], [0.26, 0.3], "cabina"), 4),
        ...canon(0.55, 0.11, 0.8),
        mastil(0.1, 0.32, 0.22, 4),
        ...chimenea(-0.12, 0.24, 0.06, 0.045),
      ],
    };
  }

  function fragata() {
    const c = { manga: 0.24, franco: 0.1, popa: 0.8, afinado: 0.25 };
    return {
      piezas: [
        casco(c), cubierta(c),
        enCapa(caja([-0.09, 0.09], [-0.5, 0.36], [0.1, 0.22], "superestructura"), 2),
        enCapa(caja([-0.08, 0.08], [0.18, 0.36], [0.22, 0.31], "superestructura"), 3),
        enCapa(caja([-0.075, 0.075], [0.355, 0.365], [0.25, 0.29], "cabina"), 4),
        ...canon(0.6, 0.1),
        mastil(0.14, 0.31, 0.3),
        ...chimenea(-0.12, 0.22),
        ...helipuerto(-0.76, 0.106, 0.075),
        // lanzadores de misiles antibuque cruzados en medio del buque
        enCapa(transformar(caja([-0.08, 0.08], [-0.33, -0.28], [0.22, 0.26], "vls"), { rz: 30, pivote: [0, -0.3, 0] }), 3),
      ],
    };
  }

  function destructor() {
    const c = { manga: 0.21, franco: 0.1, popa: 0.8, afinado: 0.3 };
    const spy = (x, y, g) => enCapa(transformar(placa([[-0.045, 0.24], [0.045, 0.24], [0.045, 0.33], [-0.045, 0.33]], 0.01, "xz", 0, "antena"), { rz: g, t: [x, y, 0] }), 4);
    return {
      piezas: [
        casco(c), cubierta(c),
        enCapa(caja([-0.08, 0.08], [-0.45, 0.34], [0.1, 0.22], "superestructura"), 2),
        enCapa(caja([-0.075, 0.075], [0.12, 0.34], [0.22, 0.36], "superestructura"), 3),
        enCapa(caja([-0.07, 0.07], [0.335, 0.345], [0.28, 0.33], "cabina"), 4),
        spy(0.05, 0.345, -40), spy(-0.05, 0.345, 40),
        // celdas de lanzamiento vertical a proa y a popa
        enCapa(caja([-0.055, 0.055], [0.42, 0.56], [0.1, 0.112], "vls"), 2),
        enCapa(caja([-0.055, 0.055], [-0.62, -0.48], [0.1, 0.112], "vls"), 2),
        ...canon(0.7, 0.1),
        mastil(0.2, 0.36, 0.3),
        ...chimenea(0.0, 0.22, 0.1, 0.045), ...chimenea(-0.28, 0.22, 0.1, 0.045),
        ...helipuerto(-0.8, 0.106, 0.065),
      ],
    };
  }

  function portaaviones() {
    const c = { manga: 0.26, franco: 0.12, popa: 0.9, afinado: 0.35 };
    const pista = [[-0.18, -1.0], [0.24, -1.0], [0.24, 0.6], [0.14, 1.0], [-0.14, 1.0], [-0.3, 0.3], [-0.3, -0.2]];
    const linea = (x0, y0, x1, y1, capa = 2) => {
      const largo = Math.hypot(x1 - x0, y1 - y0), g = (Math.atan2(x0 - x1, y1 - y0) * 180) / Math.PI;
      return enCapa(transformar(caja([-0.005, 0.005], [0, largo], [0.166, 0.169], "linea"), { rz: g, t: [x0, y0, 0] }), capa);
    };
    const avion = (x, y, g) => enCapa(transformar(placa([[0, 0.09], [0.07, -0.03], [0.02, -0.05], [-0.02, -0.05], [-0.07, -0.03]], 0.015, "xy", 0.175, "ala"), { rz: g, t: [x, y, 0] }), 3);
    return {
      piezas: [
        casco(c),
        enCapa(placa(pista, 0.03, "xy", 0.15, "vuelo"), 1),
        linea(-0.26, 0.28, 0.06, -0.95), linea(-0.22, 0.28, 0.1, -0.95),
        linea(0.04, 0.3, 0.04, 0.95),
        ...[-0.2, 0.0, 0.2].map((y) => enCapa(caja([0.03, 0.05], [y, y + 0.1], [0.166, 0.169], "linea"), 2)),
        enCapa(caja([0.15, 0.23], [-0.25, 0.08], [0.165, 0.34], "superestructura"), 3),
        enCapa(caja([0.145, 0.235], [0.075, 0.085], [0.28, 0.32], "cabina"), 4),
        enCapa(caja([0.145, 0.235], [-0.12, -0.02], [0.3, 0.33], "bando"), 4),
        enCapa([
          cilindro("z", [0.19, -0.05, 0.42], 0.012, 0.18, "metal", 5),
          placa([[0.13, 0.46], [0.25, 0.46], [0.25, 0.5], [0.13, 0.5]], 0.012, "xz", -0.05, "antena"),
        ], 5),
        avion(-0.12, 0.72, 0), avion(0.02, 0.72, 0), avion(-0.18, -0.55, 160), avion(-0.04, -0.72, 170), avion(0.12, -0.6, 175),
      ],
    };
  }

  function submarino() {
    const sec = (y, w, h) => [y, [[-w, 0], [w, 0], [w * 0.7, h * 0.7], [0, h], [-w * 0.7, h * 0.7]]];
    const vela = (y, w) => [y, rect(-w, w, 0.03, 0.26)];
    return {
      piezas: [
        secciones([sec(-1, 0.012, 0.01), sec(-0.8, 0.07, 0.06), sec(0.55, 0.1, 0.08), sec(0.85, 0.08, 0.065), sec(1, 0.02, 0.02)], "sub"),
        enCapa(secciones([vela(0.12, 0.025), vela(0.36, 0.035), vela(0.44, 0.012)], "sub"), 1),
        enCapa(placa([[-0.13, 0.26], [0.13, 0.26], [0.13, 0.32], [-0.13, 0.32]], 0.012, "xy", 0.18, "sub"), 2),
        enCapa(caja([-0.03, 0.03], [0.14, 0.42], [0.26, 0.27], "bando"), 2),
        enCapa(placa([[-0.84, 0.02], [-0.9, 0.13], [-0.97, 0.13], [-0.98, 0.02]], 0.015, "yz", 0, "sub"), 1),
      ],
    };
  }

  function buqueDesembarco() {
    const c = { manga: 0.3, franco: 0.15, popa: 0.95, afinado: 0.3 };
    return {
      piezas: [
        casco(c), cubierta(c),
        enCapa(caja([-0.13, 0.13], [-0.1, 0.5], [0.15, 0.34], "superestructura"), 2),
        enCapa(caja([-0.12, 0.12], [0.3, 0.5], [0.34, 0.42], "superestructura"), 3),
        enCapa(caja([-0.115, 0.115], [0.495, 0.505], [0.36, 0.4], "cabina"), 4),
        mastil(0.3, 0.42, 0.24),
        ...chimenea(0.05, 0.34, 0.08, 0.05),
        ...helipuerto(-0.45, 0.156, 0.075), ...helipuerto(-0.78, 0.156, 0.075),
        ...canon(0.7, 0.15, 0.8),
      ],
    };
  }

  // ================================================================ INSTALACIONES
  const bandera = (x, y, z0 = 0.02) => enCapa([
    cilindro("z", [x, y, z0 + 0.22], 0.012, 0.44, "metal", 5),
    placa([[y, z0 + 0.3], [y + 0.2, z0 + 0.3], [y + 0.2, z0 + 0.44], [y, z0 + 0.44]], 0.01, "yz", x, "bando"),
  ], 4);

  function baseAerea() {
    // pista a lo largo de y en x = -0.5; calle de rodaje paralela; plataforma, hangares y refugios al este
    const X = -0.52, ANCHO = 0.17, L = 1.08;
    const franja = (x0, x1, y0, y1, tono = "linea", capa = 2, z = 0.021) => enCapa(caja([x0, x1], [y0, y1], [z, z + 0.003], tono), capa);
    const arco = (x0, x1, h) => [[x0, 0.02], [x1, 0.02], [x1, h * 0.55], [(x0 + x1) / 2 + (x1 - x0) * 0.3, h * 0.9], [(x0 + x1) / 2, h], [(x0 + x1) / 2 - (x1 - x0) * 0.3, h * 0.9], [x0, h * 0.55]];
    const hangar = (x0, x1, y0, y1, h = 0.2) => [
      enCapa(secciones([[y0, arco(x0, x1, h)], [y1, arco(x0, x1, h)]], "techo"), 3),
      enCapa(placa([[x0 + 0.03, 0.02], [x1 - 0.03, 0.02], [x1 - 0.03, h * 0.5], [x0 + 0.03, h * 0.5]], 0.006, "xz", y1 + 0.004, "negro"), 4),
    ];
    // refugio reforzado: boveda baja de hormigon con la boca hacia la calle de rodaje (-x)
    const refugio = (xc, yc) => enCapa(transformar(secciones([
      [-0.09, [[-0.1, 0.02], [0.1, 0.02], [0.1, 0.05], [0.06, 0.1], [-0.06, 0.1], [-0.1, 0.05]]],
      [0.09, [[-0.1, 0.02], [0.1, 0.02], [0.1, 0.05], [0.06, 0.1], [-0.06, 0.1], [-0.1, 0.05]]],
    ], "concreto"), { rz: 90, t: [xc, yc, 0] }), 3);
    const jet = (x, y, g) => enCapa(transformar([
      placa([[0, 0.1], [0.02, 0.05], [0.075, -0.02], [0.075, -0.035], [0.02, -0.02], [0.018, -0.07], [0.04, -0.09], [-0.04, -0.09], [-0.018, -0.07], [-0.02, -0.02], [-0.075, -0.035], [-0.075, -0.02], [-0.02, 0.05]], 0.012, "xy", 0.028, "cuerpo"),
      placa([[-0.006, 0.07], [0.006, 0.07], [0.006, 0.035], [-0.006, 0.035]], 0.008, "xy", 0.036, "cabina"),
    ], { rz: g, t: [x, y, 0] }), 4);
    const tanque = (x, y) => enCapa([cilindro("z", [x, y, 0.06], 0.07, 0.08, "tanque", 12)], 3);
    return {
      piezas: [
        // terreno de la base y cerco perimetral
        placa([[-0.95, -1.15], [0.95, -1.15], [0.95, 1.15], [-0.95, 1.15]], 0.02, "xy", 0.0, "cesped"),
        enCapa([
          caja([-0.94, 0.94], [1.137, 1.14], [0.02, 0.04], "metal"), caja([-0.94, 0.94], [-1.14, -1.137], [0.02, 0.04], "metal"),
          caja([0.937, 0.94], [-1.14, 1.14], [0.02, 0.04], "metal"), caja([-0.94, -0.937], [-1.14, 1.14], [0.02, 0.04], "metal"),
        ], 1),
        // pista, rodaje paralelo con sus conexiones, y la plataforma
        enCapa(placa([[X - ANCHO / 2, -L], [X + ANCHO / 2, -L], [X + ANCHO / 2, L], [X - ANCHO / 2, L]], 0.01, "xy", 0.015, "pista"), 1),
        enCapa(placa([[-0.3, -0.95], [-0.24, -0.95], [-0.24, 0.95], [-0.3, 0.95]], 0.01, "xy", 0.015, "pista"), 1),
        ...[-0.95, -0.3, 0.3, 0.95].map((y) => enCapa(placa([[X, y - 0.03], [-0.24, y - 0.03], [-0.24, y + 0.03], [X, y + 0.03]], 0.01, "xy", 0.015, "pista"), 1)),
        enCapa(placa([[-0.24, -0.45], [0.42, -0.45], [0.42, 0.25], [-0.24, 0.25]], 0.01, "xy", 0.016, "concreto"), 1),
        // marcas de pista: bordes, umbrales en "piano", eje discontinuo y zona de toma de contacto
        franja(X - ANCHO / 2 + 0.006, X - ANCHO / 2 + 0.009, -L, L), franja(X + ANCHO / 2 - 0.009, X + ANCHO / 2 - 0.006, -L, L),
        ...[-0.062, -0.047, -0.032, 0.032, 0.047, 0.062].flatMap((dx) => [
          franja(X + dx - 0.004, X + dx + 0.004, L - 0.08, L - 0.02), franja(X + dx - 0.004, X + dx + 0.004, -L + 0.02, -L + 0.08)]),
        ...[-0.82, -0.62, -0.42, -0.22, -0.02, 0.18, 0.38, 0.58].map((y) => franja(X - 0.003, X + 0.003, y, y + 0.08)),
        ...[L - 0.28, -L + 0.2].flatMap((y) => [franja(X - 0.05, X - 0.035, y, y + 0.07), franja(X + 0.035, X + 0.05, y, y + 0.07)]),
        // eje amarillo del rodaje
        ...[-0.9, -0.6, -0.3, 0, 0.3, 0.6].map((y) => franja(-0.272, -0.268, y, y + 0.22, "grua")),
        // hangares, refugios, aviones en la plataforma
        ...hangar(0.46, 0.8, -0.42, -0.12), ...hangar(0.46, 0.8, -0.02, 0.26),
        refugio(0.1, 0.6), refugio(0.35, 0.6), refugio(0.6, 0.6),
        jet(-0.08, -0.3, 90), jet(0.08, -0.3, 90), jet(0.24, -0.3, 90), jet(0.08, 0.1, 90),
        // torre de control, edificio de operaciones, combustible y bandera
        enCapa(caja([0.2, 0.44], [-0.95, -0.7], [0.02, 0.14], "superestructura"), 3),
        enCapa(caja([0.2, 0.44], [-0.95, -0.7], [0.14, 0.16], "techo"), 4),
        enCapa(cilindro("z", [0.05, -0.75, 0.2], 0.045, 0.38, "concreto", 8), 3),
        enCapa(cilindro("z", [0.05, -0.75, 0.42], 0.075, 0.07, "cabina", 8), 4),
        enCapa(cilindro("z", [0.05, -0.75, 0.465], 0.08, 0.02, "techo", 8), 5),
        tanque(0.65, -0.72), tanque(0.82, -0.72), tanque(0.65, -0.9), tanque(0.82, -0.9),
        bandera(0.85, 0.95),
      ],
    };
  }

  function deposito() {
    const nave = (x0, x1, y0, y1, h) => enCapa(secciones([
      [y0, [[x0, 0.02], [x1, 0.02], [x1, h], [(x0 + x1) / 2, h + 0.12], [x0, h]]],
      [y1, [[x0, 0.02], [x1, 0.02], [x1, h], [(x0 + x1) / 2, h + 0.12], [x0, h]]],
    ], "techo"), 2);
    return {
      piezas: [
        placa([[-0.95, -0.95], [0.95, -0.95], [0.95, 0.95], [-0.95, 0.95]], 0.02, "xy", 0.0, "concreto"),
        nave(-0.8, -0.2, -0.75, 0.1, 0.22), nave(-0.8, -0.2, 0.25, 0.8, 0.22),
        ...[[0.35, -0.55], [0.72, -0.55], [0.35, -0.12], [0.72, -0.12]].map(([x, y]) => enCapa(cilindro("z", [x, y, 0.11], 0.16, 0.2, "tanque", 12), 2)),
        enCapa(caja([0.2, 0.85], [0.3, 0.75], [0.02, 0.12], "oliva"), 2),
        bandera(0.85, 0.82),
      ],
    };
  }

  function puerto() {
    const grua = (x, y) => enCapa([
      caja([x - 0.1, x - 0.07], [y - 0.05, y + 0.05], [0.02, 0.42], "grua"), caja([x + 0.07, x + 0.1], [y - 0.05, y + 0.05], [0.02, 0.42], "grua"),
      caja([x - 0.1, x + 0.1], [y - 0.05, y + 0.05], [0.42, 0.47], "grua"),
      caja([x - 0.03, x + 0.03], [y - 0.05, y + 0.55], [0.44, 0.49], "grua"),
    ], 2);
    return {
      piezas: [
        placa([[-1.0, 0.15], [1.0, 0.15], [1.0, 0.95], [-1.0, 0.95]], 0.04, "xy", 0.0, "concreto"),
        placa([[-0.12, -1.0], [0.12, -1.0], [0.12, 0.15], [-0.12, 0.15]], 0.04, "xy", 0.0, "concreto"),
        grua(-0.45, 0.35), grua(0.3, 0.35),
        enCapa(secciones([
          [0.55, [[-0.2, 0.02], [0.75, 0.02], [0.75, 0.2], [0.275, 0.3], [-0.2, 0.2]]],
          [0.88, [[-0.2, 0.02], [0.75, 0.02], [0.75, 0.2], [0.275, 0.3], [-0.2, 0.2]]],
        ], "techo"), 2),
        ...[-0.8, -0.5, -0.2].map((y) => enCapa(cilindro("z", [0.1, y, 0.04], 0.018, 0.05, "negro", 5), 1)),
        bandera(-0.9, 0.75),
      ],
    };
  }

  // ================================================================ registro
  // tam: tamaño en pantalla respecto de un caza. Los buques y las instalaciones son mas grandes; el personal, menor.
  const R = M.registrar;
  R("caza_embarcado", cazaEmbarcado, { tam: 1, modelos: ["caza_embarcado", "fa18ef"] });
  R("ataque_ligero", ataqueLigero, { tam: 0.95, clases: ["ataque"], modelos: ["ataque_ligero"] });
  R("helo_ataque", heloAtaque, { tam: 1, clases: ["helicoptero"], modelos: ["helo_ataque"] });
  R("helo_transporte", heloTransporte, { tam: 1.05, clases: ["helicoptero_artillado"], modelos: ["helo_transporte", "mh60dap"] });
  R("dron_reconocimiento", dronReconocimiento, { tam: 0.8, clases: ["dron_reconocimiento"], modelos: ["uav_reco"] });
  R("dron_armado", dronArmado, { tam: 0.9, clases: ["dron_ataque"], modelos: ["uav_armado", "mq9"] });
  R("merodeadora", merodeadora, { tam: 0.62, clases: ["municion_merodeadora"], modelos: ["merodeadora", "lucas"] });
  R("avion_ge", avionGe, { tam: 1.1, clases: ["avion_ge"], modelos: ["ge_aereo"] });
  R("misil_crucero", misilCrucero, { tam: 0.72, clases: ["misil_crucero"], modelos: ["crucero"] });
  // aeronaves de EE. UU. de la plantilla del 3 de enero de 2026 (tam: relativo a un caza)
  R("f22", f22, { tam: 1.1, modelos: ["f22"] });
  R("f35a", () => f35(false), { tam: 1, modelos: ["f35a"] });
  R("f35b", () => f35(true), { tam: 1, modelos: ["f35b"] });
  R("ea18g", () => cazaEmbarcado({ growler: true }), { tam: 1, modelos: ["ea18g"] });
  R("b1b", b1b, { tam: 2.0, modelos: ["b1b"] });
  R("p8a", () => reactorPesado({ motores: 2 }), { tam: 1.6, modelos: ["p8a"] });
  R("e3g", () => reactorPesado({ rotodomo: true }), { tam: 1.9, modelos: ["e3g"] });
  R("rc135", () => reactorPesado({ mejillas: true }), { tam: 1.9, modelos: ["rc135"] });
  R("kc135", () => reactorPesado({ pertiga: true }), { tam: 1.9, clases: ["cisterna"], modelos: ["kc135"] });
  R("ec130h", () => c130(true), { tam: 1.6, modelos: ["ec130h"] });
  R("e2d", e2d, { tam: 1.3, clases: ["alerta_temprana"], modelos: ["e2d"] });
  R("rq170", rq170, { tam: 1.1, modelos: ["rq170"] });
  R("mh47g", chinook, { tam: 1.35, modelos: ["mh47g"] });
  R("mh60m", () => heloTransporte(false), { tam: 1.05, modelos: ["mh60m"] });
  R("ah6m", () => littleBird("ah"), { tam: 0.62, modelos: ["ah6m"] });
  R("mh6m", () => littleBird("mh"), { tam: 0.62, modelos: ["mh6m"] });

  R("infanteria", infanteria, { tam: 0.72, suelo: true, clases: ["infanteria"] });
  R("antiaerea_portatil", antiaereaPortatil, { tam: 0.7, suelo: true, clases: ["antiaerea_portatil"] });
  R("tanque", tanque, { tam: 0.88, suelo: true, clases: ["blindado"] });
  R("artilleria", artilleria, { tam: 0.9, suelo: true, clases: ["artilleria"] });
  R("reconocimiento", reconocimiento, { tam: 0.82, suelo: true, clases: ["reconocimiento"] });
  R("antiaerea", antiaerea, { tam: 0.88, suelo: true, clases: ["antiaerea"] });
  R("ingenieros", ingenieros, { tam: 0.88, suelo: true, clases: ["ingenieros"] });
  R("convoy", convoy, { tam: 1.05, suelo: true, clases: ["transporte"] });
  R("radar", radar, { tam: 0.95, suelo: true, clases: ["radar"] });
  R("guerra_electronica", guerraElectronica, { tam: 0.92, suelo: true, clases: ["guerra_electronica"] });
  R("lanzador_misiles", lanzadorMisiles, { tam: 1.0, suelo: true, clases: ["lanzador_misiles"] });

  R("patrullero", patrullero, { tam: 1.15, suelo: true, clases: ["patrullero"] });
  R("fragata", fragata, { tam: 1.5, suelo: true, clases: ["fragata"] });
  R("destructor", destructor, { tam: 1.7, suelo: true, clases: ["destructor"] });
  R("portaaviones", portaaviones, { tam: 2.2, suelo: true, clases: ["portaaviones"] });
  R("submarino", submarino, { tam: 1.35, suelo: true, clases: ["submarino"] });
  R("buque_desembarco", buqueDesembarco, { tam: 1.65, suelo: true, clases: ["buque_desembarco"] });

  R("base_aerea", baseAerea, { tam: 1.9, suelo: true, rumbo: 25, clases: ["base_aerea"] });
  R("deposito", deposito, { tam: 1.45, suelo: true, rumbo: 25, clases: ["deposito"] });
  R("puerto", puerto, { tam: 1.7, suelo: true, rumbo: 25, clases: ["puerto"] });

  const api = { registradas: () => M.MALLAS };
  raiz.Miniaturas = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
