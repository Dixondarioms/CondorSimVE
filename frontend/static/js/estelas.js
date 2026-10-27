/* Estelas del Cóndor: por donde pasó cada unidad en los últimos minutos simulados, una línea que se desvanece con la
 * edad (la parte más vieja, más tenue). Se arma en el navegador con las posiciones que llegan cada segundo. */
(function (raiz) {
  "use strict";

  const MIN_KM = 0.05;  // menos que esto no es moverse (evita puntos repetidos de una unidad quieta)
  const SALTO_KM = 80;  // mas que esto entre dos posiciones seguidas es un traslado del director: la estela empieza de nuevo
  const TRAMOS = 5;     // la estela se dibuja en tramos de edad, cada uno mas tenue que el anterior
  const ATRAS_S = 120;  // un reloj que vuelve mas que esto (otro escenario, repeticion) empieza la estela de nuevo

  function distanciaKm(a, b) {
    const r = Math.PI / 180;
    const x = (b[1] - a[1]) * r * Math.cos(((a[0] + b[0]) / 2) * r);
    const y = (b[0] - a[0]) * r;
    return Math.sqrt(x * x + y * y) * 6371;
  }

  /** duracionSeg: cuanto tiempo simulado se recuerda (se puede cambiar con fijarDuracion). */
  function crear(duracionSeg = 1800) {
    let duracion = duracionSeg;
    const huellas = new Map();  // id -> [[lat, lon, seg], ...] de la mas vieja a la mas nueva

    function registrar(id, lat, lon, seg) {
      let h = huellas.get(id);
      const p = [lat, lon, seg];
      if (!h) { huellas.set(id, [p]); return; }
      const ultimo = h[h.length - 1];
      if (seg < ultimo[2] - ATRAS_S || distanciaKm(ultimo, p) > SALTO_KM) { huellas.set(id, [p]); return; }  // reloj atras o traslado
      p[2] = Math.max(seg, ultimo[2]);  // el estado completo y las posiciones pueden diferir en una fraccion de segundo
      if (distanciaKm(ultimo, p) < MIN_KM) { ultimo[2] = p[2]; return; }  // quieta: solo se actualiza la hora
      h.push(p);
    }

    /** Quita lo que ya es mas viejo que la duracion (y las unidades que ya no estan, si se da `vivas`). */
    function recortar(segAhora, vivas) {
      for (const [id, h] of huellas) {
        if (vivas && !vivas.has(id)) { huellas.delete(id); continue; }
        let i = 0;
        while (i < h.length - 1 && segAhora - h[i + 1][2] > duracion) i += 1;  // conserva un punto en el borde
        if (i) h.splice(0, i);
      }
    }

    /** Tramos de la estela de `id`: [{ puntos: [[lat, lon], ...], opacidad }] del mas viejo al mas nuevo. */
    function tramos(id, segAhora) {
      const h = huellas.get(id);
      if (!h || h.length < 2) return [];
      const salida = [];
      for (let k = 0; k < TRAMOS; k += 1) {
        const desde = segAhora - duracion * (1 - k / TRAMOS);
        const hasta = segAhora - duracion * (1 - (k + 1) / TRAMOS);
        const pts = [];
        for (let i = 0; i < h.length; i += 1) {
          const enTramo = h[i][2] >= desde && h[i][2] <= hasta;
          const siguienteEntra = i + 1 < h.length && h[i + 1][2] >= desde && h[i][2] < desde;  // une con el tramo anterior
          if (enTramo || siguienteEntra || (k === TRAMOS - 1 && h[i][2] > hasta)) pts.push([h[i][0], h[i][1]]);
        }
        if (pts.length >= 2) salida.push({ puntos: pts, opacidad: 0.12 + 0.68 * ((k + 1) / TRAMOS) });
      }
      return salida;
    }

    return {
      registrar, recortar, tramos,
      ids: () => [...huellas.keys()],
      limpiar: () => huellas.clear(),
      fijarDuracion: (s) => { duracion = s; },
      duracion: () => duracion,
    };
  }

  const api = { crear, distanciaKm };
  if (typeof module !== "undefined") module.exports = api;
  raiz.Estelas = api;
})(typeof window !== "undefined" ? window : globalThis);
