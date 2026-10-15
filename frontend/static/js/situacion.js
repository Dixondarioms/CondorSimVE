/* Pestaña Situación: cuadro radar (lo que detecta cada sensor del bando), personal (efectivos y bajas por rama) e
 * infraestructura (energía, refinación, comunicaciones y puentes), más el tiempo de recorrido de una orden de mover y
 * el porcentaje de objetivos cumplidos. Funciones puras (se prueban con Node) y el dibujo de la pestaña, que app.js
 * llama en cada estado nuevo. */
(function (raiz) {
  "use strict";

  const PERFIL = { alto: "cota alta", medio: "cota media", rasante: "rasante" };

  /** "3 h 20 min", "45 min" o "1 día 2 h" a partir de horas decimales. */
  function duracion(horas) {
    if (!(horas > 0)) return "0 min";
    const min = Math.round(horas * 60);
    const d = Math.floor(min / 1440);
    const h = Math.floor((min % 1440) / 60);
    const m = min % 60;
    const partes = [];
    if (d) partes.push(`${d} día${d > 1 ? "s" : ""}`);
    if (h) partes.push(`${h} h`);
    if (m && !d) partes.push(`${m} min`);
    return partes.join(" ") || "0 min";
  }

  /** Texto del tiempo de todo el recorrido de una orden de mover (respuesta de /ordenes/previsualizar). */
  function textoTiempo(t) {
    if (!t || !(t.km > 0)) return "";
    let s = `Recorrido completo: ${t.km} km en ${duracion(t.horas)} (${t.turnos} turno${t.turnos > 1 ? "s" : ""})`;
    if (t.llegada && !t.bloqueo) s += `; llegada estimada ${t.llegada}h${t.llegada_dias ? ` (+${t.llegada_dias} día${t.llegada_dias > 1 ? "s" : ""})` : ""}`;
    s += ".";
    if (t.bloqueo) s += ` ${t.bloqueo}`;
    else if (t.km_combustible != null && t.km > t.km_combustible) s += ` El combustible alcanza para ${t.km_combustible} km: reabastezca en el camino.`;
    return s;
  }

  /** "2 de 5 (40 %)" o "sin objetivos". */
  function textoObjetivos(m) {
    if (!m || !m.asignados) return "sin objetivos";
    return `${m.cumplidos} de ${m.asignados} cumplidos (${Math.round(m.cumplidos_pct)} %)`;
  }

  /** Una línea por contacto de un sensor: "Caza R · 85 km · rumbo 040° · cota media". */
  function lineaContacto(c, nombreClase) {
    const partes = [c.nombre || nombreClase || c.clase, `${Math.round(c.distancia_km)} km`, `rumbo ${String(c.rumbo).padStart(3, "0")}°`];
    if (c.en_vuelo && PERFIL[c.perfil]) partes.push(PERFIL[c.perfil]);
    if (c.por_escucha) partes.push("por su emisión");
    return partes.join(" · ");
  }

  /** Estado de un sensor en una frase corta. */
  function estadoSensor(s) {
    const partes = [];
    if (s.emisor === false) partes.push("escucha pasiva (no emite)");
    else partes.push(s.emitiendo ? "emitiendo" : "en silencio (solo ve a ojo)");
    if (s.interferido) partes.push("interferido");
    if (s.energia_pct != null && s.energia_pct < 100) partes.push(`energía de respaldo: ${s.energia_pct} % del alcance`);
    return partes.join(" · ");
  }

  /** Mensaje para la red del bando con el cuadro radar (cabe en un mensaje del chat: 500 caracteres). */
  function mensajeRadar(sensores, turno, hora, nombreClase = (x) => x) {
    const conContactos = sensores.filter((s) => s.contactos.length);
    if (!conContactos.length) return `Cuadro radar turno ${turno} (${hora}): sin contactos enemigos.`;
    const vistos = new Set();
    const lineas = [];
    for (const s of conContactos) {
      const nuevos = s.contactos.filter((c) => !vistos.has(c.unidad_id));
      nuevos.forEach((c) => vistos.add(c.unidad_id));
      if (nuevos.length) lineas.push(`${s.nombre}: ${nuevos.map((c) => lineaContacto(c, nombreClase(c.clase))).join("; ")}`);
    }
    let texto = `Cuadro radar turno ${turno} (${hora}), ${vistos.size} contacto(s). ${lineas.join(" | ")}`;
    if (texto.length > 500) texto = texto.slice(0, 497) + "…";
    return texto;
  }

  const api = { duracion, textoTiempo, textoObjetivos, lineaContacto, estadoSensor, mensajeRadar };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Situacion = api;
})(typeof window !== "undefined" ? window : globalThis);
