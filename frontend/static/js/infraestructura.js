/* Capa "Infraestructura": centrales eléctricas, refinerías, centros de comunicaciones y puentes estratégicos de
 * Venezuela (static/geo/venezuela/infraestructura.json, de OpenStreetMap; tools/preparar_infraestructura.py).
 * Es una capa de referencia: el instructor coloca cada instalación en el ejercicio, para un bando, con un clic en su
 * ficha. Ya colocada es una unidad fija que se puede atacar, proteger o fijar como objetivo, y su estado pesa en la
 * conducción del bando (backend/app/engine/infraestructura.py). */
(function (raiz) {
  "use strict";

  // icono de cada clase (trazos de 24 x 24) y su color
  const ICONOS = {
    termoelectrica: { color: "#e76f51", d: "M13 2 4 14h6l-1 8 9-12h-6z" },
    hidroelectrica: { color: "#219ebc", d: "M12 2C8 8 6 11 6 14a6 6 0 0 0 12 0c0-3-2-6-6-12z" },
    refineria: { color: "#f4a261", d: "M12 2c1 4-3 5-3 9a3 3 0 0 0 6 0c0-2-1-3-1-5 2 1 4 4 4 7a6 6 0 0 1-12 0c0-5 4-7 6-11z" },
    centro_comunicaciones: { color: "#9b5de5", d: "M11 10h2v12h-2zM5.6 5.6a9 9 0 0 1 12.8 0L17 7a7 7 0 0 0-10 0zM8.5 8.5a5 5 0 0 1 7 0L14 10a3 3 0 0 0-4 0z" },
    puente: { color: "#8d99ae", d: "M2 13h20v2H2zM4 15h2v6H4zM18 15h2v6h-2zM11 15h2v6h-2zM3 13a9 7 0 0 1 18 0h-2a7 5 0 0 0-14 0z" },
  };
  const NOMBRES = {
    termoelectrica: "Central termoeléctrica", hidroelectrica: "Central hidroeléctrica", refineria: "Refinería",
    centro_comunicaciones: "Centro de comunicaciones", puente: "Puente estratégico",
  };
  const EFECTO = {
    termoelectrica: "Energía: si se la daña, los radares fijos del bando pierden alcance.",
    hidroelectrica: "Energía: si se la daña, los radares fijos del bando pierden alcance.",
    refineria: "Combustible: si se la daña, los depósitos del bando reponen menos combustible.",
    centro_comunicaciones: "Comunicaciones: si se lo daña, más órdenes del bando no llegan a tiempo.",
    puente: "Movilidad: con menos del 50 % de fuerza queda cortado y nadie cruza por él.",
  };

  /** La instalación del ejercicio que ya ocupa ese lugar (misma clase, a menos de 1 km), o null. */
  function enEjercicio(unidades, p) {
    const cerca = (u) => Math.hypot(u.lat - p.lat, (u.lon - p.lon) * Math.cos((p.lat * Math.PI) / 180)) * 111.32 < 1;
    return (unidades || []).find((u) => u.clase === p.clase && u.estado !== "destruida" && cerca(u)) || null;
  }

  /** Filas [rotulo, valor] de la ficha de una instalación. */
  function filasFicha(p) {
    const filas = [["Tipo", NOMBRES[p.clase] || p.clase]];
    if (p.capacidad) filas.push(["Capacidad", p.capacidad]);
    if (p.combustible) filas.push(["Combustible", p.combustible]);
    if (p.largo_km) filas.push(["Largo", `${String(p.largo_km).replace(".", ",")} km`]);
    if (p.operador) filas.push(["Operador", p.operador]);
    filas.push(["Coordenadas", `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}${p.aproximada ? " (aproximadas)" : ""}`]);
    return filas;
  }

  function crear(ctx) {
    const el = (tag, cls = "", texto = "") => { const e = document.createElement(tag); if (cls) e.className = cls; if (texto) e.textContent = texto; return e; };
    let datos = null;

    function icono(p) {
      const i = ICONOS[p.clase] || ICONOS.puente;
      return L.divIcon({
        className: "icono-infra", iconSize: [28, 28], iconAnchor: [14, 14],
        html: `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style="background:${i.color}"><path d="${i.d}"/></svg>`,
      });
    }

    function ficha(p) {
      const div = el("div", "popup-base popup-infra");
      div.append(el("b", "", p.nombre));
      const dl = el("dl", "specs");
      for (const [k, v] of filasFicha(p)) { const d = el("div"); d.append(el("dt", "", k), el("dd", "", v)); dl.appendChild(d); }
      div.appendChild(dl);
      if (p.descripcion) div.appendChild(el("p", "ayuda", p.descripcion));
      div.appendChild(el("p", "nota", EFECTO[p.clase] || ""));
      const existente = enEjercicio((ctx.datos() || {}).unidades, p);
      const usuario = ctx.usuario();
      if (existente) {
        div.appendChild(el("p", "nota", `En el ejercicio: ${existente.nombre} (bando ${existente.bando}).`));
      } else if (usuario && usuario.rol === "instructor" && ctx.escenarioId()) {
        div.appendChild(el("p", "ayuda", "Colóquela en el ejercicio, del lado del bando al que sirve:"));
        const fila = el("div", "fila");
        for (const bando of ["azul", "rojo"]) {
          const b = el("button", `mini ${bando}`, bando === "azul" ? "Bando Azul" : "Bando Rojo");
          b.type = "button";
          b.addEventListener("click", async () => {
            const cuerpo = { nombre: p.nombre, bando, clase: p.clase, lat: p.lat, lon: p.lon };
            if (p.radio_km) cuerpo.radio_km = p.radio_km;
            try {
              await ctx.api("POST", ctx.rutaEsc("/unidades"), cuerpo);
              ctx.map().closePopup();
              ctx.toast(`${p.nombre} colocada en el ejercicio (bando ${bando}).`, true);
            } catch (_) { /* toast ya mostrado */ }
          });
          fila.appendChild(b);
        }
        div.appendChild(fila);
      } else {
        div.appendChild(el("p", "ayuda", "Capa de referencia: solo forma parte del ejercicio si el instructor la coloca."));
      }
      div.appendChild(el("p", "credito", "Ubicación: © colaboradores de OpenStreetMap"));
      return div;
    }

    async function cargar() {
      if (datos) return;
      try {
        const r = await fetch("/static/geo/venezuela/infraestructura.json");
        if (!r.ok) return;
        datos = await r.json();
      } catch (_) { return; }
      const capa = ctx.capa();
      for (const p of datos.instalaciones || []) {
        const m = L.marker([p.lat, p.lon], { icon: icono(p), keyboard: false, riseOnHover: true });
        m.bindTooltip(p.nombre, { direction: "right", offset: [10, 0], className: "nombre-base" });
        m.bindPopup(() => ficha(p), { minWidth: 240, autoPanPaddingTopLeft: [20, 60], autoPanPaddingBottomRight: [290, 20] });
        capa.addLayer(m);
      }
    }

    return { cargar, instalaciones: () => (datos ? datos.instalaciones : []) };
  }

  const api = { crear, enEjercicio, filasFicha, ICONOS, NOMBRES };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Infraestructura = api;
})(typeof window !== "undefined" ? window : globalThis);
