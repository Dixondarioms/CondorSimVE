/* Miniaturas 3D de las unidades para el mapa.
 *
 * F-16 y Su-30: imagenes renderizadas de modelos 3D reales (24 rumbos cada uno, ver tools/sprites3d y
 * frontend/static/aeronaves/CREDITOS.md). Cualquier otra unidad (aeronaves, buques, vehiculos, instalaciones) es
 * una malla procedural: las de este archivo son los cazas; el resto se registra desde js/miniaturas.js con
 * `registrar()` usando las primitivas exportadas en `primitivas`. Todo es puro y se prueba con Node.
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
  // Paleta: [r, g, b] o [r, g, b, alfa]. "deriva" y "bando" toman el color del bando.
  const COLOR = {
    cuerpo: [142, 153, 166], ala: [122, 134, 149], toma: [58, 63, 72], cabina: [38, 62, 104],
    azul: [58, 134, 255], rojo: [239, 35, 60], neutro: [203, 213, 225],
    // buques
    casco: [118, 128, 138], cubierta: [88, 94, 100], vuelo: [64, 68, 74], superestructura: [150, 158, 166],
    linea: [236, 236, 226], sub: [46, 50, 56], vls: [52, 56, 62],
    // vehiculos y personal
    oliva: [96, 108, 64], oliva2: [76, 86, 50], oruga: [46, 46, 42], caucho: [34, 34, 34], metal: [104, 108, 104],
    lona: [126, 118, 84], uniforme: [92, 100, 70], piel: [196, 160, 128],
    // sensores, armas e instalaciones
    antena: [196, 202, 210], radomo: [222, 224, 220], misil: [226, 228, 232], negro: [30, 30, 32],
    concreto: [158, 158, 152], pista: [66, 68, 72], techo: [112, 122, 116], tanque: [196, 196, 186],
    grua: [214, 172, 44], cesped: [104, 122, 84],
    // helices y rotores (translucidos)
    rotor: [30, 30, 30, 0.28], pala: [40, 40, 40],
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
  // `capa`: las piezas de una capa mayor se pintan siempre despues (encima) de las de una capa menor. Sirve para
  // lo que esta apoyado sobre una superficie grande (superestructura sobre la cubierta, torreta sobre el casco),
  // donde el orden por profundidad de cada cara falla. Las aeronaves usan todas la capa 0.
  function pieza(caras, tono, cx, capa = 0) {
    const c = cx || centro(caras.reduce((a, f) => a.concat(f), []));
    return {
      tono, capa,
      caras: caras.map((f) => (punto(normal(f), restar(centro(f), c)) < 0 ? f.slice().reverse() : f)),
    };
  }

  /** La misma pieza (o lista de piezas) en otra capa. */
  function enCapa(p, capa) {
    if (Array.isArray(p)) return p.map((x) => enCapa(x, capa));
    return { ...p, capa };
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
    // "xy": horizontal (p = [x, y]); "yz": vertical longitudinal (p = [y, z]); "xz": vertical transversal (p = [x, z])
    const en = (p, lado) => (plano === "xy"
      ? [p[0], p[1], desplazamiento + lado * h]
      : plano === "xz" ? [p[0], desplazamiento + lado * h, p[1]]
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

  /** Solido por secciones transversales: [[y, [[x, z], ...]], ...], todas con el mismo numero de puntos
   * (cascos de buques, chasis con frente inclinado, torretas). */
  function secciones(lista, tono) {
    const anillos = lista.map(([y, pts]) => pts.map(([x, z]) => [x, y, z]));
    const n = anillos[0].length;
    const caras = [anillos[0].slice(), anillos[anillos.length - 1].slice()];
    for (let i = 0; i < anillos.length - 1; i++) {
      for (let k = 0; k < n; k++) {
        caras.push([anillos[i][k], anillos[i][(k + 1) % n], anillos[i + 1][(k + 1) % n], anillos[i + 1][k]]);
      }
    }
    return pieza(caras, tono);
  }

  /** Cilindro (o tronco de cono) a lo largo de un eje ("x", "y" o "z"), centrado en `c`. */
  function cilindro(eje, c, radio, largo, tono, n = 10, radio2 = radio) {
    const anillo2 = (t, r) => Array.from({ length: n }, (_, k) => {
      const a = (2 * Math.PI * k) / n;
      const u = r * Math.cos(a), v = r * Math.sin(a);
      if (eje === "x") return [c[0] + t, c[1] + u, c[2] + v];
      if (eje === "y") return [c[0] + u, c[1] + t, c[2] + v];
      return [c[0] + u, c[1] + v, c[2] + t];
    });
    const a = anillo2(-largo / 2, radio), b = anillo2(largo / 2, radio2);
    const caras = [a.slice(), b.slice()];
    for (let k = 0; k < n; k++) caras.push([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]]);
    return pieza(caras, tono, c);
  }

  /** Esfera (o elipsoide) de poca resolucion: cupulas de radar, cabezas, cascos. */
  function esfera(c, r, tono, n = 8, achatado = 1) {
    const cortes = [-0.92, -0.6, 0, 0.6, 0.92];
    return fuselaje(cortes.map((t) => {
      const w = 2 * r * Math.sqrt(1 - t * t);
      return [c[1] + t * r, w, w * achatado, c[2]];
    }), tono, c[0], n);
  }

  /** Disco horizontal delgado (rotores, helices de empuje en el plano xz con `plano`). */
  function disco(c, r, tono, plano = "xy", n = 14) {
    const contorno = Array.from({ length: n }, (_, k) => {
      const a = (2 * Math.PI * k) / n;
      return [r * Math.cos(a), r * Math.sin(a)];
    });
    if (plano === "xy") return placa(contorno.map(([u, v]) => [c[0] + u, c[1] + v]), 0.01, "xy", c[2], tono);
    if (plano === "yz") return placa(contorno.map(([u, v]) => [c[1] + u, c[2] + v]), 0.01, "yz", c[0], tono);
    return placa(contorno.map(([u, v]) => [c[0] + u, c[2] + v]), 0.01, "xz", c[1], tono);
  }

  /** Gira (grados) y traslada una pieza o lista de piezas. Orden: `rx` (cabeceo, alrededor del eje x), `ry`
   * (alabeo), `rz` (guiñada, positivo = hacia babor), todo alrededor de `pivote`, y luego se suma `t`. */
  function transformar(p, { rx = 0, ry = 0, rz = 0, pivote = [0, 0, 0], t = [0, 0, 0], escala = 1 } = {}) {
    if (Array.isArray(p)) return p.map((x) => transformar(x, { rx, ry, rz, pivote, t, escala }));
    const r = Math.PI / 180;
    const [cx, sx, cy, sy, cz, sz] = [Math.cos(rx * r), Math.sin(rx * r), Math.cos(ry * r), Math.sin(ry * r), Math.cos(rz * r), Math.sin(rz * r)];
    const mover = ([x0, y0, z0]) => {
      let x = (x0 - pivote[0]) * escala, y = (y0 - pivote[1]) * escala, z = (z0 - pivote[2]) * escala;
      [y, z] = [y * cx - z * sx, y * sx + z * cx];
      [x, z] = [x * cy + z * sy, -x * sy + z * cy];
      [x, y] = [x * cz - y * sz, x * sz + y * cz];
      return [x + pivote[0] + t[0], y + pivote[1] + t[1], z + pivote[2] + t[2]];
    };
    return { ...p, caras: p.caras.map((f) => f.map(mover)) };
  }

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
  // Por malla: `tam` (tamaño en pantalla relativo al de un caza), `suelo` (apoyada en tierra o en el agua: lleva
  // una peana del color del bando en lugar de la sombra de vuelo) y `rumbo` fijo (instalaciones que no giran).
  const INFO = { f16: { tam: 1 }, su30: { tam: 1 }, generico: { tam: 1 } };
  const POR_MODELO = {};
  const POR_CLASE = { caza: "generico", ataque: "generico" };
  const memoria = {};
  const tieneMalla = (id) => Object.prototype.hasOwnProperty.call(MALLAS, id);
  const malla = (id) => {
    if (memoria[id]) return memoria[id];
    const m = MALLAS[id]();
    return (memoria[id] = { ...m, piezas: m.piezas.flat(Infinity) }); // las mallas pueden anidar listas de piezas
  };
  const info = (id) => INFO[id] || { tam: 1 };

  /**
   * Agrega una malla al catalogo de miniaturas. `crear()` devuelve { piezas, radio? }; `clases` y `modelos` son los
   * ids del catalogo del servidor que se dibujan con ella.
   */
  function registrar(id, crear, { tam = 1, suelo = false, rumbo = null, clases = [], modelos = [] } = {}) {
    MALLAS[id] = crear;
    INFO[id] = { tam, suelo, rumbo };
    delete memoria[id];
    for (const c of clases) POR_CLASE[c] = id;
    for (const m of modelos) POR_MODELO[m] = id;
  }

  /** Malla que corresponde a una unidad: la de su modelo, la de su clase, o null si no hay miniatura. */
  function mallaPara(u) {
    if (!u) return null;
    if (u.modelo && tieneMalla(u.modelo)) return u.modelo;
    if (u.modelo && Object.prototype.hasOwnProperty.call(POR_MODELO, u.modelo)) return POR_MODELO[u.modelo];
    return Object.prototype.hasOwnProperty.call(POR_CLASE, u.clase) ? POR_CLASE[u.clase] : null;
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
    const id = tieneMalla(modelo) ? modelo : "generico";
    const m = malla(id);
    if (info(id).suelo) n = 1; // los grupos en formacion son solo de aeronaves
    const th = (((rumbo % 360) + 360) % 360) * (Math.PI / 180);
    const c = Math.cos(th), s = Math.sin(th);
    const sp = Math.sin(PITCH), cp = Math.cos(PITCH);
    const esc = escalaGrupo(n);
    const vista = [0, cp, -sp]; // direccion en la que mira la camara (hacia el norte y abajo)
    const guiar = (x, y, z) => [x * c + y * s, -x * s + y * c, z]; // rumbo: proa (0,1) -> (sin th, cos th)
    const caras = [];
    let radio = 0;
    for (const [ox, oy] of formacion(n)) {
      const [gx, gy] = [ox * c + oy * s, -ox * s + oy * c]; // desplazamiento del avion dentro de la formacion
      for (const p of m.piezas) {
        const base = p.tono === "deriva" || p.tono === "bando" ? COLOR[bando] || COLOR.neutro : COLOR[p.tono] || COLOR.cuerpo;
        for (const cara of p.caras) {
          const mundo = cara.map(([x, y, z]) => {
            const g = guiar(x * esc, y * esc, z * esc);
            return [g[0] + gx, g[1] + gy, g[2]];
          });
          const nv = normal(mundo);
          const translucida = base.length > 3; // rotores y helices: se ve el suelo a traves
          if (punto(nv, vista) >= 0) continue; // cara trasera
          const luz = AMBIENTE + (1 - AMBIENTE) * Math.max(0, punto(nv, LUZ));
          const proj = mundo.map(([x, y, z]) => [x, -(y * sp + z * cp)]);
          for (const [px, py] of proj) radio = Math.max(radio, Math.hypot(px, py));
          const ctr = centro(mundo);
          const relleno = [Math.round(base[0] * luz), Math.round(base[1] * luz), Math.round(base[2] * luz)];
          if (translucida) relleno.push(base[3]);
          caras.push({
            puntos: proj,
            relleno,
            capa: p.capa || 0,
            profundidad: ctr[1] * cp - ctr[2] * sp, // mayor = mas lejos de la camara
          });
        }
      }
    }
    caras.sort((a, b) => (a.capa - b.capa) || (b.profundidad - a.profundidad));
    return { caras, radio: Math.max(radio, radioDe(id) * esc) };
  }

  /** Radio del cuadro de una malla: el declarado, o el mayor radio proyectado en 24 rumbos (calculado una vez). */
  const radios = {};
  function radioDe(id) {
    const m = malla(id);
    if (m.radio) return m.radio;
    if (radios[id]) return radios[id];
    const sp = Math.sin(PITCH), cp = Math.cos(PITCH);
    let r = 0;
    for (let k = 0; k < 24; k++) {
      const th = (k * 15 * Math.PI) / 180, c = Math.cos(th), s = Math.sin(th);
      for (const p of m.piezas) for (const f of p.caras) for (const [x, y, z] of f) {
        const gx = x * c + y * s, gy = -x * s + y * c;
        r = Math.max(r, Math.hypot(gx, gy * sp + z * cp));
      }
    }
    radios[id] = r;
    return r;
  }

  /** Semilado del cuadro del SVG para un grupo de n aviones: constante con el rumbo (no "respira" al girar). */
  function semilado(modelo, n) {
    const id = tieneMalla(modelo) ? modelo : "generico";
    if (info(id).suelo) n = 1;
    const esc = escalaGrupo(n);
    const extremo = formacion(n).reduce((a, [x, y]) => Math.max(a, Math.hypot(x, y)), 0);
    return (extremo + radioDe(id) * esc) * 1.06;
  }

  const rgb = ([r, g, b, a]) => (a === undefined ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${a})`);
  const COLOR_PEANA = { azul: "58,134,255", rojo: "239,35,60", neutro: "203,213,225" };

  /** Huella (radio en planta) de una malla apoyada en el suelo: la peana la rodea. */
  const huellas = {};
  function huella(id) {
    if (huellas[id]) return huellas[id];
    let r = 0;
    for (const p of malla(id).piezas) for (const f of p.caras) for (const [x, y] of f) r = Math.max(r, Math.hypot(x, y));
    return (huellas[id] = r);
  }

  /** SVG (cadena) de la miniatura; `px` es el lado del cuadrado en pixeles. */
  function svg(op = {}) {
    const modelo = tieneMalla(op.modelo) ? op.modelo : mallaPara(op) || "generico";
    const px = op.px || 54;
    const n = op.n || 1;
    const h = semilado(modelo, n);
    const bando = op.bando || "neutro";
    const { caras } = proyectar({ modelo, rumbo: op.rumbo || 0, bando, n });
    const f = (v) => (Math.round(v * 1000) / 1000).toString();
    const trazo = (0.02 * h).toFixed(4);
    const poligonos = caras.map((c) => {
      const color = rgb(c.relleno);
      const borde = c.relleno.length > 3 ? "" : ` stroke="${color}" stroke-width="${trazo}" stroke-linejoin="round"`;
      return `<polygon points="${c.puntos.map(([x, y]) => `${f(x)},${f(y)}`).join(" ")}" fill="${color}"${borde}/>`;
    }).join("");
    let fondo;
    if (info(modelo).suelo) {
      // peana: circulo en el suelo (elipse en la vista inclinada) con el color del bando
      const r = Math.min(h * 0.98, huella(modelo) * 1.08);
      const cp = COLOR_PEANA[bando] || COLOR_PEANA.neutro;
      fondo = `<ellipse cx="0" cy="0" rx="${f(r)}" ry="${f(r * Math.sin(PITCH))}" fill="rgba(${cp},.22)" stroke="rgba(${cp},.95)" stroke-width="${f(h * 0.035)}"/>`;
    } else {
      fondo = `<ellipse cx="${f(h * 0.12)}" cy="${f(h * 0.5)}" rx="${f(h * 0.6)}" ry="${f(h * 0.2)}" fill="rgba(0,0,0,.28)"/>`;
    }
    return `<svg class="avion3d-svg" xmlns="http://www.w3.org/2000/svg" viewBox="${f(-h)} ${f(-h)} ${f(2 * h)} ${f(2 * h)}" width="${px}" height="${px}" aria-hidden="true">`
      + `${fondo}${poligonos}</svg>`;
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

  /** Rumbo con el que se dibuja la malla: el fijo de las instalaciones o el pedido. */
  const rumboDibujo = (id, r) => (info(id).rumbo === null || info(id).rumbo === undefined ? r : info(id).rumbo);

  /** Tamaño relativo (respecto de un caza) con que se dibuja la miniatura de una unidad. */
  const tamRelativo = (u) => { const id = mallaPara(u); return id ? info(id).tam : 1; };

  /**
   * Marcador de una unidad: { html, ancho, alto }. F-16 y Su-30 con sus imagenes reales; el resto con su malla
   * procedural. `base`: pixeles del cuadro de un caza solo; cada malla lo escala con su `tam`.
   */
  function marcador({ modelo, clase, rumbo = 0, bando = "neutro", n = 1, base = 50 } = {}) {
    if (tieneSprite(modelo)) {
      const d = disposicion({ modelo, rumbo, n, base });
      const imgs = d.imagenes.map((i) => `<img src="${i.url}" alt="" draggable="false" style="left:${i.x}px;top:${i.y}px;width:${i.lado}px;height:${i.lado}px">`).join("");
      return { html: `<div class="avion3d-grupo ${bando}" style="width:${d.ancho}px;height:${d.alto}px">${imgs}</div>`, ancho: d.ancho, alto: d.alto };
    }
    const id = mallaPara({ modelo, clase }) || "generico";
    const suelo = !!info(id).suelo;
    const px = tamanoSugerido(base * info(id).tam, suelo ? 1 : n);
    return { html: svg({ modelo: id, rumbo: rumboDibujo(id, rumbo), bando, n: suelo ? 1 : n, px }), ancho: px, alto: px, suelo };
  }

  /** Si la miniatura de esa unidad gira con su rumbo (las instalaciones fijas no). */
  const gira = (u) => { const id = mallaPara(u); return !!id && (info(id).rumbo === null || info(id).rumbo === undefined); };

  const primitivas = { pieza, enCapa, fuselaje, placa, caja, espejo, secciones, cilindro, esfera, disco, transformar };

  const api = {
    svg, proyectar, semilado, mallaPara, formacion, rumbo, tamanoSugerido, marcador, disposicion, urlSprite, tieneSprite,
    registrar, primitivas, tamRelativo, gira, info,
    get MALLAS() { return Object.keys(MALLAS); },
    SPRITES: Object.keys(SPRITES), PASO_RUMBO,
  };
  raiz.Modelo3d = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
