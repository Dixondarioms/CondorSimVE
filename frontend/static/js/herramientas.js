/* Herramientas de mapa: regla para medir distancias y rumbos. `medir` es pura (se prueba con Node);
 * `crear` conecta la regla con el mapa de Leaflet. */
(function (raiz) {
  "use strict";

  const RAD = Math.PI / 180;

  /** Distancia en km entre dos puntos [lat, lon] (Haversine). */
  function distanciaKm(a, b) {
    const h = Math.sin(((b[0] - a[0]) * RAD) / 2) ** 2
      + Math.cos(a[0] * RAD) * Math.cos(b[0] * RAD) * Math.sin(((b[1] - a[1]) * RAD) / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(h));
  }

  /** Rumbo inicial en grados [0, 360) de a hacia b (0 = norte, 90 = este). */
  function rumbo(a, b) {
    const y = Math.sin((b[1] - a[1]) * RAD) * Math.cos(b[0] * RAD);
    const x = Math.cos(a[0] * RAD) * Math.sin(b[0] * RAD) - Math.sin(a[0] * RAD) * Math.cos(b[0] * RAD) * Math.cos((b[1] - a[1]) * RAD);
    return (((Math.atan2(y, x) / RAD) % 360) + 360) % 360;
  }

  const PUNTOS_CARDINALES = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  const cardinal = (grados) => PUNTOS_CARDINALES[Math.round((((grados % 360) + 360) % 360) / 45) % 8];

  /** Tramos de una poligonal [[lat, lon], ...]: distancia y rumbo de cada uno, y la distancia acumulada. */
  function medir(puntos) {
    const tramos = [];
    let total = 0;
    for (let i = 1; i < puntos.length; i++) {
      const km = distanciaKm(puntos[i - 1], puntos[i]);
      total += km;
      tramos.push({ desde: puntos[i - 1], hasta: puntos[i], km, rumbo: rumbo(puntos[i - 1], puntos[i]), acumulado: total });
    }
    return { tramos, total };
  }

  /** Texto de un tramo: "12.3 km · 045° NE". */
  const textoTramo = (t) => `${t.km.toFixed(1)} km · ${String(Math.round(t.rumbo)).padStart(3, "0")}° ${cardinal(t.rumbo)}`;

  /** ctx: { map(), alMedir(bool) }. Botones: #btn-regla (activa/termina) y #btn-regla-limpiar; texto en #regla-info. */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const grupo = L.layerGroup();
    let puntos = [];
    let activa = false;

    function pintar() {
      grupo.clearLayers();
      if (!puntos.length) { $("regla-info").textContent = activa ? "Haga clic en el mapa para empezar a medir." : ""; return; }
      const { tramos, total } = medir(puntos);
      if (puntos.length > 1) L.polyline(puntos, { color: "#ffffff", weight: 3, dashArray: "8 6", interactive: false }).addTo(grupo);
      puntos.forEach((p, i) => L.circleMarker(p, { radius: 4, color: "#fff", weight: 2, fillColor: "#FFB703", fillOpacity: 1, interactive: false }).addTo(grupo)
        .bindTooltip(i === 0 ? "Inicio" : `${tramos[i - 1].acumulado.toFixed(1)} km`, { permanent: i > 0, direction: "top", className: "etiqueta-regla" }));
      tramos.forEach((t) => L.marker([(t.desde[0] + t.hasta[0]) / 2, (t.desde[1] + t.hasta[1]) / 2], {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: "tramo-regla", html: `<span>${textoTramo(t)}</span>`, iconSize: [0, 0] }),
      }).addTo(grupo));
      $("regla-info").textContent = `Total ${total.toFixed(1)} km` + (tramos.length ? ` · último tramo ${textoTramo(tramos[tramos.length - 1])}` : "");
    }

    function alClic(e) { puntos.push([e.latlng.lat, e.latlng.lng]); pintar(); }

    function empezar() {
      activa = true;
      puntos = [];
      ctx.map().doubleClickZoom.disable();
      ctx.map().on("click", alClic);
      ctx.map().getContainer().classList.add("midiendo");
      ctx.alMedir(true);
      $("btn-regla").classList.add("activa");
      $("btn-regla-limpiar").hidden = false;
      pintar();
    }

    function terminar() {
      if (!activa) return;
      activa = false;
      ctx.map().off("click", alClic);
      ctx.map().doubleClickZoom.enable();
      ctx.map().getContainer().classList.remove("midiendo");
      $("btn-regla").classList.remove("activa");
      setTimeout(() => ctx.alMedir(false), 60); // el ultimo clic de la medicion no debe contar como clic de mapa
      if (!puntos.length) $("btn-regla-limpiar").hidden = true;
      pintar();
    }

    function limpiar() {
      puntos = [];
      grupo.clearLayers();
      if (!activa) $("btn-regla-limpiar").hidden = true;
      pintar();
    }

    function conectar() {
      grupo.addTo(ctx.map());
      $("btn-regla").addEventListener("click", () => (activa ? terminar() : empezar()));
      $("btn-regla-limpiar").addEventListener("click", limpiar);
      document.addEventListener("keydown", (e) => { if (e.key === "Escape" && activa) terminar(); });
      ctx.map().on("dblclick", () => { if (activa) terminar(); });
    }

    return { conectar, terminar, limpiar, activa: () => activa };
  }

  /** Convertidor de unidades (#btn-convertir, #convertidor): distancia, velocidad, altura, masa y volumen. */
  function crearConvertidor() {
    const $ = (id) => document.getElementById(id);
    const boton = $("btn-convertir");
    if (!boton || !raiz.Logica) return;
    const U = raiz.Logica.UNIDADES;
    const magnitud = $("cv-magnitud");
    const unidad = $("cv-unidad");
    const valor = $("cv-valor");
    const lista = $("cv-resultados");
    magnitud.innerHTML = Object.entries(U).map(([k, m]) => `<option value="${k}">${m.nombre}</option>`).join("");
    const llenarUnidades = () => {
      unidad.innerHTML = Object.entries(U[magnitud.value].unidades).map(([k, u]) => `<option value="${k}">${u[0]}</option>`).join("");
    };
    const calcular = () => {
      const m = magnitud.value;
      const v = parseFloat(String(valor.value).replace(",", "."));
      lista.innerHTML = Number.isFinite(v)
        ? Object.entries(U[m].unidades).filter(([k]) => k !== unidad.value)
          .map(([k, u]) => `<li><b>${raiz.Logica.convertir(m, v, unidad.value, k).toLocaleString("es", { maximumFractionDigits: 3 })}</b> ${u[0]}</li>`).join("")
        : "";
    };
    magnitud.addEventListener("change", () => { llenarUnidades(); calcular(); });
    unidad.addEventListener("change", calcular);
    valor.addEventListener("input", calcular);
    boton.addEventListener("click", () => {
      const panel = $("convertidor");
      panel.hidden = !panel.hidden;
      boton.setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden) valor.focus();
    });
    llenarUnidades();
    calcular();
  }

  const api = { medir, distanciaKm, rumbo, cardinal, textoTramo, crear, crearConvertidor };
  raiz.Herramientas = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
