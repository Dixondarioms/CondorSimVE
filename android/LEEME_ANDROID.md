# Cóndor en una tablet Android

El Cóndor completo (servidor, mapas, satélite, fotos y base de datos) funciona dentro de la tablet, sin la PC y sin
internet. Se instala una sola vez, con internet, usando la aplicación gratuita **Termux**.

Requisitos: Android 8 o más nuevo, unos **5 GB libres** (2 GB del paquete y 3 GB para instalarlo; el paquete se puede
borrar después) y una pantalla de 10 pulgadas o más (se usa en horizontal).

## 1. En la PC: armar el paquete

```
backend\venv\Scripts\python tools\empaquetar_android.py
```

Deja `dist\Condor_Android.zip` (unos 2 GB) con **una copia de la base de esta PC**: la tablet empieza con los mismos
ejercicios y cuentas. Con `--sin-base` la tablet empieza con una base nueva (usuario `admin` y la contraseña inicial del
Cóndor, que pide cambiar al primer ingreso).

## 2. En la tablet: instalar las aplicaciones

Desde **F-Droid** (https://f-droid.org; la versión de Termux de Play Store está desactualizada y no sirve):

- **Termux**
- **Termux:Widget** (para el acceso directo «Condor» en la pantalla de inicio)

## 3. Copiar el paquete

**Forma corta:** copie a **Descargas** de la tablet `Condor_Android.zip` y `instalar_desde_zip.sh` (los dos quedan en
`dist`), abra Termux y escriba `termux-setup-storage` y luego `bash ~/storage/downloads/instalar_desde_zip.sh`:
descomprime e instala todo solo (y deja el registro en Descargas/condor_instalacion.log). Si usa esta forma, salte al
paso 5.

**Forma manual:**

Pase `Condor_Android.zip` a la carpeta **Descargas** de la tablet (cable USB, pendrive con adaptador OTG o tarjeta) y
**descomprímalo ahí** con el administrador de archivos: queda la carpeta `Descargas/Condor_Android`. Si el
administrador de archivos no puede (son muchos archivos), descomprímalo desde Termux después de
`termux-setup-storage`: `pkg install unzip` y luego `unzip ~/storage/downloads/Condor_Android.zip -d ~/storage/downloads`.

## 4. Instalar (con internet, una sola vez)

Abra Termux y escriba, una línea por vez:

```
termux-setup-storage
bash ~/storage/downloads/Condor_Android/android/instalar_condor.sh
```

La primera línea pide permiso para leer Descargas: acéptelo. La segunda instala Python y copia el Cóndor; **tarda de 15
a 40 minutos** la primera vez porque compila una parte. Deje la tablet enchufada y con la pantalla encendida.

## 5. Usar el Cóndor

- Ponga el widget de **Termux:Widget** en la pantalla de inicio y toque **Condor**: arranca el servidor y abre el
  navegador en `http://127.0.0.1:8001`. (O escriba `condor` en Termux.)
- En el navegador (Chrome), menú ⋮ → **Agregar a la pantalla de inicio**: queda el ícono del Cóndor y se abre a
  pantalla completa, como una aplicación.
- Para apagarlo: widget **Detener Condor** (o `detener-condor` en Termux). Los ejercicios quedan guardados.

## Usar la tablet como servidor del aula

Con la tablet y los demás equipos en la misma red wifi, abra Termux y escriba:

```
detener-condor
CONDOR_RED=1 condor
```

Muestra la dirección (por ejemplo `http://192.168.1.20:8001`) para abrir desde las otras tablets, celulares o PC.

## Actualizar

Arme un paquete nuevo en la PC, cópielo y descomprímalo igual que la primera vez, y repita el paso 4: la base de datos
de la tablet se conserva (no se reemplaza por la de la PC). Para usar la de la PC, borre antes
`~/condor/backend/simulador_fenix.db` en Termux.

## Si algo falla

- **«No arrancó»**: el detalle está en `~/condor/backend/condor.log` (en Termux: `tail -40 ~/condor/backend/condor.log`).
- **Se cierra al apagar la pantalla**: en Ajustes de Android → Aplicaciones → Termux → Batería, elija **Sin
  restricciones**.
- **Falla la instalación de pydantic**: ejecute de nuevo el paso 4 (continúa donde quedó); necesita internet estable.
