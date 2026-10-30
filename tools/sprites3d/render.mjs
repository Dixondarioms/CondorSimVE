/* Renderiza un modelo .glb de aeronave a imagenes (sprites) para el mapa del simulador.
 *
 *   ?modelo=f16&modo=inspeccion          vistas superior, lateral y frontal (para elegir el eje de la proa)
 *   ?modelo=f16&modo=render&nariz=-z&largo=14.5&marco=13&pasos=24&px=256
 *                                        genera un PNG por rumbo (0, 15, ... 345) y los guarda via POST /guardar
 *
 * Camara ortografica inclinada 42 grados y vista desde el sur, igual que el modelo procedural (modelo3d.js):
 * la proa apunta al "norte" de la imagen cuando el rumbo es 0 y gira en sentido horario. El tamaño es real
 * (`largo` en metros y `marco` = semilado del cuadro en metros), asi que un Su-33 se ve mayor que un F-16. */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const q = new URLSearchParams(location.search);
const id = q.get("modelo") || "f16";
const modo = q.get("modo") || "inspeccion";
const px = Number(q.get("px") || 256);
const pasos = Number(q.get("pasos") || 24);
const estado = document.getElementById("estado");
const vistas = document.getElementById("vistas");
const log = (t) => { estado.textContent += `\n${t}`; };
const PITCH = (42 * Math.PI) / 180;

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(px, px);
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const escena = new THREE.Scene();
escena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
escena.environmentIntensity = 0.55;
const sol = new THREE.DirectionalLight(0xffffff, 2.4);
sol.position.set(-0.45, 0.84, 0.3).multiplyScalar(40); // arriba, desde el oeste y algo hacia la camara (sur = +z)
escena.add(sol);
escena.add(new THREE.HemisphereLight(0xe3ecff, 0x59636f, 0.7));

// Las partes del modelo (glb con su pintura; STL u OBJ sin ella: se pintan de un solo tono, ?color=rrggbb).
const pintura = new THREE.MeshStandardMaterial({ color: new THREE.Color(`#${q.get("color") || "8e99a6"}`), roughness: 0.62, metalness: 0.18 });
async function cargarParte({ url, ext }) {
  if (ext === "stl") {
    const geo = await new STLLoader().loadAsync(url);
    geo.computeVertexNormals();
    return new THREE.Mesh(geo, pintura);
  }
  if (ext === "obj") {
    const obj = await new OBJLoader().loadAsync(url);
    obj.traverse((o) => { if (o.isMesh) { o.geometry.computeVertexNormals(); o.material = pintura; } });
    return obj;
  }
  return (await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(url)).scene; // glb comprimidos (glTF-Transform)
}
log(`Cargando las partes de ${id} ...`);
const partes = await (await fetch(`/partes/${id}`)).json();
const modelo = new THREE.Group();
for (const p of partes) modelo.add(await cargarParte(p));
// los STL suelen venir con Z hacia arriba (impresion 3D): ?arriba=z los endereza (Y arriba, como glTF); ?rotz=90 gira
// sobre Z los que vienen acostados de costado
if (q.get("arriba") === "z") modelo.rotation.x = -Math.PI / 2;
if (q.get("rotz")) modelo.rotation.z = (Number(q.get("rotz")) * Math.PI) / 180;
// ?pintar=1: un solo tono tambien para los glb (p. ej. para quitar escarapelas o libreas ajenas)
if (q.get("pintar")) modelo.traverse((o) => { if (o.isMesh) o.material = pintura; });
escena.add(modelo);
modelo.updateMatrixWorld(true);
const caja = new THREE.Box3().setFromObject(modelo);
const tam = caja.getSize(new THREE.Vector3());
const centro = caja.getCenter(new THREE.Vector3());
let triangulos = 0;
modelo.traverse((o) => { if (o.isMesh) { triangulos += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3; } });
log(`Modelo ${id}: caja ${tam.x.toFixed(2)} x ${tam.y.toFixed(2)} x ${tam.z.toFixed(2)} (x,y,z), ${Math.round(triangulos)} triangulos.`);
modelo.position.sub(centro); // centrado en el origen

function camara(marco) {
  return new THREE.OrthographicCamera(-marco, marco, marco, -marco, 0.1, 400);
}

if (modo === "inspeccion") {
  const marco = Math.max(tam.x, tam.y, tam.z) * 0.62;
  const cam = camara(marco);
  const vista = (nombre, pos, arriba) => {
    cam.position.set(...pos);
    cam.up.set(...arriba);
    cam.lookAt(0, 0, 0);
    renderer.render(escena, cam);
    const c = document.createElement("canvas");
    c.width = c.height = px / 2;
    c.getContext("2d").drawImage(renderer.domElement, 0, 0, px / 2, px / 2);
    const fig = document.createElement("figure");
    fig.style.margin = "2px";
    fig.append(c, Object.assign(document.createElement("figcaption"), { textContent: nombre }));
    vistas.appendChild(fig);
  };
  vista("desde +y (arriba): x a la derecha, -z hacia arriba", [0, 100, 0], [0, 0, -1]);
  vista("desde +x (costado): -z a la izquierda", [100, 0, 0], [0, 1, 0]);
  vista("desde +z (frente/atras): x a la derecha", [0, 0, 100], [0, 1, 0]);
  log("Listo. Elija el eje de la proa (nariz=+x|-x|+z|-z) mirando la vista superior.");
} else {
  // ---- render de sprites
  const nariz = q.get("nariz") || "-z";
  const largo = Number(q.get("largo") || 15);
  const marcoPedido = q.get("marco") || "13";
  const eje = { "+x": [1, 0, 0], "-x": [-1, 0, 0], "+z": [0, 0, 1], "-z": [0, 0, -1] }[nariz];
  const alineador = new THREE.Group();
  escena.remove(modelo);
  alineador.add(modelo);
  const giro = new THREE.Group();
  giro.add(alineador);
  escena.add(giro);
  alineador.quaternion.setFromUnitVectors(new THREE.Vector3(...eje), new THREE.Vector3(0, 0, -1)); // proa al norte (-z)
  const largoModelo = Math.abs(eje[0]) ? tam.x : tam.z;
  alineador.scale.setScalar(largo / largoModelo);
  // marco=auto: el cuadro justo para que el modelo quepa en cualquier rumbo (radio horizontal + algo de su altura)
  giro.updateMatrixWorld(true);
  const caja2 = new THREE.Box3().setFromObject(giro).getSize(new THREE.Vector3());
  const marco = marcoPedido === "auto"
    ? Math.round((1.04 * Math.hypot(caja2.x / 2, caja2.z / 2) + 0.35 * caja2.y) * 100) / 100
    : Number(marcoPedido);
  const cam = camara(marco);
  cam.position.set(0, Math.sin(PITCH) * 100, Math.cos(PITCH) * 100);
  cam.lookAt(0, 0, 0);
  log(`Render de ${id}: nariz ${nariz}, largo ${largo} m (escala ${(largo / largoModelo).toFixed(4)}), marco ±${marco} m, ${pasos} rumbos.`);
  for (let i = 0; i < pasos; i++) {
    const rumbo = (360 / pasos) * i;
    giro.rotation.y = -(rumbo * Math.PI) / 180; // rumbo horario visto desde arriba
    renderer.render(escena, cam);
    const blob = await new Promise((r) => renderer.domElement.toBlob(r, "image/png"));
    const nombre = `${id}_${String(Math.round(rumbo)).padStart(3, "0")}.png`;
    const resp = await fetch(`/guardar?nombre=${nombre}`, { method: "POST", body: blob });
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    c.getContext("2d").drawImage(renderer.domElement, 0, 0, 64, 64);
    vistas.appendChild(c);
    if (!resp.ok) { log(`ERROR guardando ${nombre}: ${resp.status}`); break; }
  }
  log(`Terminado: ${pasos} imagenes de ${id} guardadas.`);
  document.title = `LISTO ${id} marco=${marco}`;
}
