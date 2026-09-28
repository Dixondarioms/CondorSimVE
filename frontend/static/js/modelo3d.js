/* Imagen 3D de las aeronaves para el mapa.
 *
 * F-16 y Su-30: imagenes renderizadas de modelos 3D reales (24 rumbos cada uno, ver tools/sprites3d y
 * frontend/static/aeronaves/CREDITOS.md). Cualquier otra aeronave (p. ej. un caza enemigo sin identificar) usa el
 * respaldo procedural de abajo. Todo es puro y se prueba con Node.
 *
 * Respaldo procedural. Sin librerias ni archivos de modelos: cada avion es una malla de
 * poligonos 3D (fuselaje, cabina, alas, derivas...) que se gira segun su rumbo, se proyecta en perspectiva
 * ortografica (camara inclinada) y se sombrea; el resultado es un SVG pequeño. Las funciones son puras y se
 * prueban con Node. Las formas son estilizadas (reconocibles, no planos tecnicos):
 *   f16   monomotor, ala en flecha, una deriva.
 *   su30  bimotor, canards, dos derivas, mayor tamaño.
 *   generico  caza sencillo para aeronaves sin modelo (p. ej. enemigos no identificados). */
(function (raiz) {
  "use strict";

  const PITCH = (42 * Math.PI) / 180; // inclinacion de la camara sobre el horizonte
  const LUZ = normalizar([-0.45, -0.3, 0.84]); // sol arriba a la izquierda y algo hacia la camara
  const AMBIENTE = 0.42;
  const COLOR = {
    cuerpo: [142, 153, 166], ala: [122, 134, 149], toma: [58, 63, 72], cabina: [38, 62, 104],
    azul: [58, 134, 255], rojo: [239, 35, 60], neutro: [203, 213, 225],
  };

  // ---------------------------------------------------------------- algebra minima
  function normalizar(v) {
    const l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  }
  const restar = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const punto = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const centro = (pts) => {
    const s = pts.reduce((a, p) => [a[0] + p[0], a[1] + p[1], a[2] + p[2]], [0, 0, 0]);
    return [s[0] / pts.length, s[1] / pts.length, s[2] / pts.length];
  };

  /** Normal (metodo de Newell) de un poligono; robusta para poligonos no triangulares. */
  function normal(pts) {
    let x = 0, y = 0, z = 0;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      x += (a[1] - b[1]) * (a[2] + b[2]);
      y += (a[2] - b[2]) * (a[0] + b[0]);
      z += (a[0] - b[0]) * (a[1] + b[1]);
    }
    return normalizar([x, y, z]);
  }

  // ---------------------------------------------------------------- constructores de piezas
  // Una pieza es { caras: [[[x,y,z],...],...], tono } con las caras orientadas hacia afuera.
  // x: derecha (estribor), y: proa, z: arriba. La pieza es convexa (o casi), asi que basta comprobar
  // que cada cara mire lejos del centro de la pieza.
  function pieza(caras, tono, cx) {
    const c = cx || centro(caras.reduce((a, f) => a.concat(f), []));
    return {
      tono,
      caras: caras.map((f) => (punto(normal(f), restar(centro(f), c)) < 0 ? f.slice().reverse() : f)),
    };
  }

  /** Anillo elipsoidal (n lados) en el plano y. */
  const anillo = (y, ancho, alto, zc, xc, n) => Array.from({ length: n }, (_, k) => {
    const a = (2 * Math.PI * k) / n;
    return [xc + (ancho / 2) * Math.cos(a), y, zc + (alto / 2) * Math.sin(a)];
  });

  /** Fuselaje: secciones [y, ancho, alto, zc] unidas en cuadrilateros, con tapas en los extremos. */
  function fuselaje(secciones, tono, xc = 0, n = 8) {
    const anillos = secciones.map(([y, w, h, z]) => anillo(y, w, h, z || 0, xc, n));
    const caras = [anillos[0].slice(), anillos[anillos.length - 1].slice()];
    for (let i = 0; i < anillos.length - 1; i++) {
      for (let k = 0; k < n; k++) {
        caras.push([anillos[i][k], anillos[i][(k + 1) % n], anillos[i + 1][(k + 1) % n], anillos[i + 1][k]]);
      }
    }
    return pieza(caras, tono);
  }

  /** Prisma a partir de un contorno convexo 2D y un espesor. `plano`: "xy" (ala, horizontal) o "yz" (deriva). */
  function placa(contorno, espesor, plano, desplazamiento, tono) {
    const h = espesor / 2;
    const en = (p, lado) => (plano === "xy"
      ? [p[0], p[1], desplazamiento + lado * h]
      : [desplazamiento + lado * h, p[0], p[1]]);
    const sup = contorno.map((p) => en(p, 1));
    const inf = contorno.map((p) => en(p, -1));
    const caras = [sup, inf];
    for (let i = 0; i < contorno.length; i++) {
      const j = (i + 1) % contorno.length;
      caras.push([sup[i], sup[j], inf[j], inf[i]]);
    }
    return pieza(caras, tono);
  }

  /** Caja alineada con los ejes: [x0,x1], [y0,y1], [z0,z1]. */
  function caja([x0, x1], [y0, y1], [z0, z1], tono) {
    const v = [
      [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
      [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ];
    return pieza([[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]], [v[0], v[1], v[5], v[4]],
      [v[1], v[2], v[6], v[5]], [v[2], v[3], v[7], v[6]], [v[3], v[0], v[4], v[7]]], tono);
  }

  const espejo = (contorno) => contorno.map(([x, y]) => [-x, y]);

  // ---------------------------------------------------------------- las tres mallas
  function mallaF16() {
    const ala = [[0.14, 0.1], [0.66, -0.42], [0.66, -0.62], [0.14, -0.62]];
    const estab = [[0.15, -0.6], [0.42, -0.86], [0.42, -0.96], [0.15, -0.96]];
    return {
      radio: 1.12,
      piezas: [
        fuselaje([[1.0, 0.04, 0.04], [0.78, 0.16, 0.16], [0.45, 0.26, 0.26], [0.1, 0.3, 0.3], [-0.3, 0.28, 0.26], [-0.75, 0.22, 0.22], [-1.0, 0.18, 0.18]], "cuerpo"),
        fuselaje([[0.58, 0.05, 0.03, 0.13], [0.36, 0.2, 0.14, 0.16], [0.1, 0.2, 0.12, 0.16], [-0.06, 0.06, 0.03, 0.13]], "cabina"),
        caja([-0.11, 0.11], [0.05, 0.4], [-0.3, -0.1], "toma"),
        placa(ala, 0.035, "xy", -0.02, "ala"), placa(espejo(ala), 0.035, "xy", -0.02, "ala"),
        placa(estab, 0.03, "xy", -0.02, "ala"), placa(espejo(estab), 0.03, "xy", -0.02, "ala"),
        placa([[-0.35, 0.13], [-0.72, 0.58], [-0.9, 0.58], [-0.92, 0.13]], 0.035, "yz", 0, "deriva"),
      ],
    };
  }

  function mallaSu30() {
    const ala = [[0.22, 0.2], [0.85, -0.55], [0.85, -0.75], [0.22, -0.7]];
    const canard = [[0.2, 0.55], [0.5, 0.4], [0.5, 0.32], [0.2, 0.36]];
    const estab = [[0.3, -0.7], [0.62, -0.92], [0.62, -1.02], [0.3, -1.02]];
    const deriva = [[-0.55, 0.12], [-0.9, 0.62], [-1.05, 0.62], [-1.05, 0.12]];
    return {
      radio: 1.3,
      piezas: [
        fuselaje([[1.0, 0.04, 0.04], [0.8, 0.2, 0.16], [0.5, 0.34, 0.24, 0.02], [0.1, 0.44, 0.24], [-0.35, 0.44, 0.24], [-0.7, 0.3, 0.2]], "cuerpo"),
        fuselaje([[0.1, 0.22, 0.22, -0.02], [-0.6, 0.24, 0.22, -0.02], [-1.05, 0.2, 0.2, -0.02]], "cuerpo", 0.2),
        fuselaje([[0.1, 0.22, 0.22, -0.02], [-0.6, 0.24, 0.22, -0.02], [-1.05, 0.2, 0.2, -0.02]], "cuerpo", -0.2),
        fuselaje([[0.7, 0.06, 0.04, 0.14], [0.5, 0.22, 0.17, 0.17], [-0.05, 0.24, 0.15, 0.17], [-0.25, 0.06, 0.04, 0.14]], "cabina"),
        caja([0.14, 0.32], [-0.05, 0.35], [-0.22, -0.06], "toma"), caja([-0.32, -0.14], [-0.05, 0.35], [-0.22, -0.06], "toma"),
        placa(ala, 0.04, "xy", 0, "ala"), placa(espejo(ala), 0.04, "xy", 0, "ala"),
        placa(canard, 0.03, "xy", 0.06, "ala"), placa(espejo(canard), 0.03, "xy", 0.06, "ala"),
        placa(estab, 0.03, "xy", -0.02, "ala"), placa(espejo(estab), 0.03, "xy", -0.02, "ala"),
        placa(deriva, 0.035, "yz", 0.36, "deriva"), placa(deriva, 0.035, "yz", -0.36, "deriva"),
      ],
    };
  }

  function mallaGenerico() {
    const ala = [[0.12, 0.35], [0.72, -0.75], [0.72, -0.85], [0.12, -0.85]];
    return {
      radio: 1.1,
      piezas: [
        fuselaje([[1.0, 0.04, 0.04], [0.7, 0.16, 0.16], [0.3, 0.26, 0.24], [-0.3, 0.26, 0.24], [-1.0, 0.18, 0.18]], "cuerpo"),
        fuselaje([[0.45, 0.05, 0.03, 0.12], [0.25, 0.18, 0.13, 0.14], [0.0, 0.18, 0.1, 0.14], [-0.15, 0.05, 0.03, 0.11]], "cabina"),
        placa(ala, 0.035, "xy", -0.02, "ala"), placa(espejo(ala), 0.035, "xy", -0.02, "ala"),
        placa([[-0.45, 0.12], [-0.8, 0.5], [-0.98, 0.5], [-1.0, 0.12]], 0.035, "yz", 0, "deriva"),
      ],
    };
  }

  const MALLAS = { f16: mallaF16, su30: mallaSu30, generico: mallaGenerico };
  const memoria = {};
  const malla = (id) => memoria[id] || (memoria[id] = MALLAS[id]());

  /** Malla que corresponde a una unidad: su modelo, o el caza generico para cazas/ataque sin modelo. */
  function mallaPara(u) {
    if (!u) return null;
    if (u.modelo && MALLAS[u.modelo]) return u.modelo;
    return u.clase === "caza" || u.clase === "ataque" ? "generico" : null;
  }

  /** Posiciones (x, y) de cada avion del grupo en el sistema local (y = proa). */
  function formacion(n) {
    const k = Math.max(1, Math.min(4, Math.round(n || 1)));
    if (k === 1) return [[0, 0]];
    if (k === 2) return [[-0.75, 0.2], [0.75, -0.5]];
    if (k === 3) return [[0, 0.6], [-1.05, -0.55], [1.05, -0.55]];
    return [[0, 0.8], [-1.1, -0.3], [1.1, -0.3], [0, -1.4]];
  }
  const escalaGrupo = (n) => (Math.max(1, Math.min(4, Math.round(n || 1))) === 1 ? 1 : 0.62);

  // ---------------------------------------------------------------- proyeccion y sombreado
  /**
   * Calcula los poligonos ya proyectados, de atras hacia adelante (algoritmo del pintor).
   * `rumbo`: grados desde el norte, en sentido horario (hacia donde apunta la proa en el mapa).
   * Devuelve { caras: [{ puntos: [[x,y],...], relleno: [r,g,b], profundidad }], radio }.
   */
  function proyectar({ modelo = "generico", rumbo = 0, bando = "neutro", n = 1 } = {}) {
    const m = malla(MALLAS[modelo] ? modelo : "generico");
    const th = (((rumbo % 360) + 360) % 360) * (Math.PI / 180);
    const c = Math.cos(th), s = Math.sin(th);
    const sp = Math.sin(PITCH), cp = Math.cos(PITCH);
    const esc = escalaGrupo(n) * (modelo === "su30" ? 1 : 1);
    const vista = [0, cp, -sp]; // direccion en la que mira la camara (hacia el norte y abajo)
    const guiar = (x, y, z) => [x * c + y * s, -x * s + y * c, z]; // rumbo: proa (0,1) -> (sin th, cos th)
    const caras = [];
    let radio = 0;
    for (const [ox, oy] of formacion(n)) {
      const [gx, gy] = [ox * c + oy * s, -ox * s + oy * c]; // desplazamiento del avion dentro de la formacion
      for (const p of m.piezas) {
        const base = p.tono === "deriva" ? COLOR[bando] || COLOR.neutro : COLOR[p.tono];
        for (const cara of p.caras) {
          const mundo = cara.map(([x, y, z]) => {
            const g = guiar(x * esc, y * esc, z * esc);
            return [g[0] + gx, g[1] + gy, g[2]];
          });
          const nv = normal(mundo);
          if (punto(nv, vista) >= 0) continue; // cara trasera
          const luz = AMBIENTE + (1 - AMBIENTE) * Math.max(0, punto(nv, LUZ));
          const proj = mundo.map(([x, y, z]) => [x, -(y * sp + z * cp)]);
          for (const [px, py] of proj) radio = Math.max(radio, Math.hypot(px, py));
          const ctr = centro(mundo);
          caras.push({
            puntos: proj,
            relleno: [Math.round(base[0] * luz), Math.round(base[1] * luz), Math.round(base[2] * luz)],
            profundidad: ctr[1] * cp - ctr[2] * sp, // mayor = mas lejos de la camara
          });
        }
      }
    }
    caras.sort((a, b) => b.profundidad - a.profundidad);
    return { caras, radio: Math.max(radio, m.radio * esc) };
  }

  /** Semilado del cuadro del SVG para un grupo de n aviones: constante con el rumbo (no "respira" al girar). */
  function semilado(modelo, n) {
    const m = malla(MALLAS[modelo] ? modelo : "generico");
    const esc = escalaGrupo(n);
    const extremo = formacion(n).reduce((a, [x, y]) => Math.max(a, Math.hypot(x, y)), 0);
    return (extremo + m.radio * esc) * 1.06;
  }

  const rgb = ([r, g, b]) => `rgb(${r},${g},${b})`;

  /** SVG (cadena) de la aeronave; `px` es el lado del cuadrado en pixeles. */
  function svg(op = {}) {
    const modelo = MALLAS[op.modelo] ? op.modelo : mallaPara(op) || "generico";
    const px = op.px || 54;
    const h = semilado(modelo, op.n || 1);
    const { caras } = proyectar({ modelo, rumbo: op.rumbo || 0, bando: op.bando || "neutro", n: op.n || 1 });
    const f = (v) => (Math.round(v * 1000) / 1000).toString();
    const poligonos = caras.map((c) => {
      const color = rgb(c.relleno);
      return `<polygon points="${c.puntos.map(([x, y]) => `${f(x)},${f(y)}`).join(" ")}" fill="${color}" stroke="${color}" stroke-width="0.02" stroke-linejoin="round"/>`;
    }).join("");
    return `<svg class="avion3d-svg" xmlns="http://www.w3.org/2000/svg" viewBox="${f(-h)} ${f(-h)} ${f(2 * h)} ${f(2 * h)}" width="${px}" height="${px}" aria-hidden="true">`
      + `<ellipse cx="${f(h * 0.12)}" cy="${f(h * 0.5)}" rx="${f(h * 0.6)}" ry="${f(h * 0.2)}" fill="rgba(0,0,0,.28)"/>${poligonos}</svg>`;
  }

  /** Rumbo inicial en grados [0, 360) del punto 1 al punto 2 (0 = norte, 90 = este). */
  function rumbo(lat1, lon1, lat2, lon2) {
    const r = Math.PI / 180;
    const y = Math.sin((lon2 - lon1) * r) * Math.cos(lat2 * r);
    const x = Math.cos(lat1 * r) * Math.sin(lat2 * r) - Math.sin(lat1 * r) * Math.cos(lat2 * r) * Math.cos((lon2 - lon1) * r);
    return (((Math.atan2(y, x) * 180) / Math.PI) + 360) % 360;
  }

  /** Lado en pixeles para un grupo: cada avion se dibuja mas chico en formacion, asi que el cuadro crece. */
  const tamanoSugerido = (base, n) => Math.round(base * ((n || 1) <= 1 ? 1 : n === 2 ? 1.35 : 1.65));

  // ---------------------------------------------------------------- sprites de modelos 3D reales
  // `marco`: semilado (m) del cuadro con el que se renderizo cada imagen; el tamaño real se conserva porque
  // todas las imagenes se dibujan a la misma escala de pixeles por metro.
  const SPRITES = { f16: { marco: 9.6 }, su30: { marco: 14 } };
  const PASO_RUMBO = 15;
  const MARCO_REF = 14; // el cuadro del Su-30 (28 m) equivale al tamaño base en pixeles
  const SEPARACION_M = 9; // metros que representa una unidad de la formacion
  const RUTA_SPRITES = "/static/aeronaves";

  const tieneSprite = (modelo) => Object.prototype.hasOwnProperty.call(SPRITES, modelo);

  /** Imagen del modelo para un rumbo cualquiera (se elige la de 15 grados mas cercana). */
  function urlSprite(modelo, rumbo) {
    const paso = Math.round((((rumbo % 360) + 360) % 360) / PASO_RUMBO) % (360 / PASO_RUMBO);
    return `${RUTA_SPRITES}/${modelo}_${String(paso * PASO_RUMBO).padStart(3, "0")}.png`;
  }

  /**
   * Disposicion de un grupo con sprites: cada imagen con su posicion y tamaño en pixeles dentro de un cuadro.
   * `base`: pixeles que mide el cuadro de un Su-30 solo. Devuelve { ancho, alto, imagenes: [{ url, x, y, lado }] }.
   */
  function disposicion({ modelo, rumbo = 0, n = 1, base = 50 } = {}) {
    const ppm = base / (2 * MARCO_REF);
    const lado = 2 * SPRITES[modelo].marco * ppm;
    const th = (((rumbo % 360) + 360) % 360) * (Math.PI / 180);
    const c = Math.cos(th), s = Math.sin(th);
    const sp = Math.sin(PITCH);
    const puestos = formacion(n).map(([ox, oy]) => {
      const gx = (ox * c + oy * s) * SEPARACION_M, gy = (-ox * s + oy * c) * SEPARACION_M; // metros: este, norte
      return { x: gx * ppm, y: -gy * sp * ppm, norte: gy };
    });
    // lado constante con el rumbo: radio maximo de la formacion (sin la compresion vertical) mas medio sprite
    const radio = formacion(n).reduce((a, [ox, oy]) => Math.max(a, Math.hypot(ox, oy)), 0) * SEPARACION_M * ppm;
    const ancho = Math.ceil(2 * radio + lado);
    puestos.sort((a, b) => b.norte - a.norte); // lo mas al norte (lejos de la camara) se dibuja primero
    return {
      ancho, alto: ancho,
      imagenes: puestos.map((p) => ({ url: urlSprite(modelo, rumbo), x: Math.round(ancho / 2 + p.x - lado / 2), y: Math.round(ancho / 2 + p.y - lado / 2), lado: Math.round(lado) })),
    };
  }

  /** Marcador de una aeronave: { html, ancho, alto } (imagenes reales si hay sprite, si no el respaldo procedural). */
  function marcador({ modelo, clase, rumbo = 0, bando = "neutro", n = 1, base = 50 } = {}) {
    if (tieneSprite(modelo)) {
      const d = disposicion({ modelo, rumbo, n, base });
      const imgs = d.imagenes.map((i) => `<img src="${i.url}" alt="" draggable="false" style="left:${i.x}px;top:${i.y}px;width:${i.lado}px;height:${i.lado}px">`).join("");
      return { html: `<div class="avion3d-grupo ${bando}" style="width:${d.ancho}px;height:${d.alto}px">${imgs}</div>`, ancho: d.ancho, alto: d.alto };
    }
    const px = tamanoSugerido(base, n);
    return { html: svg({ modelo, clase, rumbo, bando, n, px }), ancho: px, alto: px };
  }

  const api = {
    svg, proyectar, semilado, mallaPara, formacion, rumbo, tamanoSugerido, marcador, disposicion, urlSprite, tieneSprite,
    MALLAS: Object.keys(MALLAS), SPRITES: Object.keys(SPRITES), PASO_RUMBO,
  };
  raiz.Modelo3d = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
