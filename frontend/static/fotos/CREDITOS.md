# Créditos de las fotografías

Las fotos de aeronaves están redimensionadas (máx. 720 px) y se distribuyen bajo las licencias de sus autores.
Se muestran con su crédito en el selector de aeronaves. Si se reemplaza una foto, actualice también su entrada
en `backend/app/engine/catalogo.py` (`MODELOS`).

| Archivo | Obra | Autor | Licencia | Origen |
|---|---|---|---|---|
| `f16.jpg` | F-16 venezolano | Veronidae | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:F-16_venezolano.jpg |
| `su30.jpg` | Sukhoi Su-30MK2 de Venezuela | Carlos E. Perez S.L | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Sukhoi_Su-30MK2_de_Venezuela.jpg |

Ambas se obtuvieron de Wikimedia Commons; se redimensionaron y se recortaron sobre el fondo uniforme de las fotos del simulador (`tools/fotos/fotos_referencia.py --uniformar`; originales en `tools/fotos/originales/`).

## Ilustraciones propias (drones, guerra electrónica, aviación embarcada y misiles)

Los modelos genéricos (drones, avión de guerra electrónica, aviación embarcada, ataque ligero y misil de crucero)
no representan un producto real, así que no
usan fotos: son ilustraciones vectoriales hechas para este proyecto y se ceden al dominio público
([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)).

| Archivo | Modelo del catálogo |
|---|---|
| `dron_reconocimiento.svg` | `uav_reco` · Dron de reconocimiento (UAV táctico) |
| `dron_armado.svg` | `uav_armado` · Dron armado (UAV de media altitud) |
| `municion_merodeadora.svg` | `merodeadora` · Munición merodeadora (dron kamikaze) |
| `avion_ge.svg` | `ge_aereo` · Avión de guerra electrónica (interferidor) |
| `caza_embarcado.svg` | `caza_embarcado` · Caza embarcado (genérico) |
| `helo_ataque.svg` | `helo_ataque` · Helicóptero de ataque (genérico) |
| `helo_transporte.svg` | `helo_transporte` · Helicóptero de transporte artillado (genérico) |
| `ataque_ligero.svg` | `ataque_ligero` · Avión de ataque ligero (genérico) |
| `crucero.svg` | `crucero` · Misil de crucero (genérico) |

Las ilustraciones se reemplazan por fotos reales, y los buques reciben la suya, con
`tools/fotos/fotos_referencia.py` (doble clic en `tools\fotos\descargar_fotos.cmd`, necesita internet): sus
créditos se agregan abajo y en `referencias.json`.

<!-- referencias:inicio -->
## Fotos de referencia (Wikimedia Commons)

Descargadas por `tools/fotos/fotos_referencia.py`, reducidas y recortadas sobre un fondo uniforme (los originales reducidos están en `tools/fotos/originales/`). Donde la FANB no tiene el equipo, la foto es un ejemplo real que sirve de referencia; las cifras del simulador siguen siendo genéricas.

| Archivo | Unidad | Obra | Autor | Licencia | Origen |
|---|---|---|---|---|---|
| `ref_ataque_ligero.jpg` | `ataque_ligero` · Avion de ataque ligero | 19334 Hongdu K-8W Karakorum Bangladesh - Air Force VGHS | Md Shaifuzzaman Ayon | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:19334_Hongdu_K-8W_Karakorum_Bangladesh_-_Air_Force_VGHS.jpg |
| `ref_helo_ataque.jpg` | `helo_ataque` · Helicoptero de ataque | Mil Mi-35M (51 yellow) | Yevgeny Volkov | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0) | https://commons.wikimedia.org/wiki/File:Mil_Mi-35M_(51_yellow).jpg |
| `ref_helo_transporte.jpg` | `helo_transporte` · Helicoptero de transporte artillado | Mil Mi-17V5 (EV) (30895405051) | Carlos E. Pérez S.L. from Maracay, Venezuela | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0) | https://commons.wikimedia.org/wiki/File:Mil_Mi-17V5_(EV)_(30895405051).jpg |
| `ref_uav_reco.jpg` | `uav_reco` · Dron de reconocimiento | Insitu ScanEagle – 2017 Sola Airshow (28630372098) | Alan Wilson from Stilton, Peterborough, Cambs, UK | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0) | https://commons.wikimedia.org/wiki/File:Insitu_ScanEagle_%E2%80%93_2017_Sola_Airshow_(28630372098).jpg |
| `ref_uav_armado.jpg` | `uav_armado` · Dron armado | 7-(Drone Mohajer 6- Army ground force)-پهپاد مهاجر 6- نیروی زمینی ارتش | Mehr News Agency | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) | https://commons.wikimedia.org/wiki/File:7-(Drone_Mohajer_6-_Army_ground_force)-%D9%BE%D9%87%D9%BE%D8%A7%D8%AF_%D9%85%D9%87%D8%A7%D8%AC%D8%B1_6-_%D9%86%DB%8C%D8%B1%D9%88%DB%8C_%D8%B2%D9%85%DB%8C%D9%86%DB%8C_%D8%A7%D8%B1%D8%AA%D8%B4.jpg |
| `ref_merodeadora.jpg` | `merodeadora` · Municion merodeadora | IAI Harop PAS 2013 02 | Julian Herzog (Website) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) | https://commons.wikimedia.org/wiki/File:IAI_Harop_PAS_2013_02.jpg |
| `ref_ge_aereo.jpg` | `ge_aereo` · Avion de guerra electronica | EC-130H Compass Call 060617 | Mil | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:EC-130H_Compass_Call_060617.jpg |
| `ref_caza_embarcado.jpg` | `caza_embarcado` · Caza embarcado | F-18F after launch from USS Abraham Lincoln (CVN-72) | U.S. Navy photo by Mass Communication Specialist 2nd Class James R. Evans | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:F-18F_after_launch_from_USS_Abraham_Lincoln_(CVN-72).jpg |
| `ref_crucero.jpg` | `crucero` · Misil de crucero | Tomahawk Block IV cruise missile -crop | U.S. Navy derivative work: The High Fin Sperm Whale | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:Tomahawk_Block_IV_cruise_missile_-crop.jpg |
| `ref_fragata.jpg` | `fragata` · Fragata | ARV Mariscal Sucre (F-21) - 1987-09857 | PH3 JEFFREY W. LOSHAW | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:ARV_Mariscal_Sucre_(F-21)_-_1987-09857.jpg |
| `ref_patrullero.jpg` | `patrullero` · Patrullero | ANBV Yavire (GC-22) | Luis García Curado, Cádiz | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:ANBV_Yavire_(GC-22).jpg |
| `ref_destructor.jpg` | `destructor` · Destructor | US Navy 110930-N-QN361-146 The Arleigh Burke-class guided-missile destroyer USS Sterett (DDG 104) is underway conducting a composite training unit | U.S. Navy photo by Mass Communication Specialist 3rd Class Jerine Lee | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:US_Navy_110930-N-QN361-146_The_Arleigh_Burke-class_guided-missile_destroyer_USS_Sterett_(DDG_104)_is_underway_conducting_a_composite_training_unit.jpg |
| `ref_portaaviones.jpg` | `portaaviones` · Portaaviones | Flickr - Official U.S. Navy Imagery - The Nimitz-class aircraft carrier USS Carl Vinson (CVN 70) is underway in the Arabian Sea. | Official Navy Page from United States of America MC2 James R. Evans/U.S. Navy | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:Flickr_-_Official_U.S._Navy_Imagery_-_The_Nimitz-class_aircraft_carrier_USS_Carl_Vinson_(CVN_70)_is_underway_in_the_Arabian_Sea..jpg |
| `ref_submarino.jpg` | `submarino` · Submarino | Submarino Oceánico Tipo U-209 S-31 Sabalo | Carlos E. Perez S.L | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Submarino_Oce%C3%A1nico_Tipo_U-209_S-31_Sabalo.JPG |
| `ref_buque_desembarco.jpg` | `buque_desembarco` · Buque de desembarco anfibio | Buque de desembarque tipo LST clase Capana - T-63 Goajira | Carlos E. Perez S.L | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Buque_de_desembarque_tipo_LST_clase_Capana_-_T-63_Goajira.JPG |
<!-- referencias:fin -->

## Aeronaves de EE. UU. de la plantilla del 3 de enero de 2026

Ilustraciones propias, estilizadas a partir de las miniaturas 3D del simulador (no son fotografías ni planos técnicos), generadas con `node tools/generar_fotos_miniaturas.js` y cedidas al dominio público ([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)).

| Archivo | Modelo del catálogo |
|---|---|
| `f22.svg` | `f22` · F-22A Raptor |
| `f35a.svg` | `f35a` · F-35A Lightning II |
| `f35b.svg` | `f35b` · F-35B Lightning II (STOVL) |
| `fa18ef.svg` | `fa18ef` · F/A-18E/F Super Hornet |
| `ea18g.svg` | `ea18g` · EA-18G Growler |
| `b1b.svg` | `b1b` · B-1B Lancer |
| `p8a.svg` | `p8a` · P-8A Poseidon |
| `e2d.svg` | `e2d` · E-2D Advanced Hawkeye |
| `e3g.svg` | `e3g` · E-3G Sentry (AWACS) |
| `rc135.svg` | `rc135` · RC-135V/W Rivet Joint |
| `ec130h.svg` | `ec130h` · EC-130H Compass Call |
| `kc135.svg` | `kc135` · KC-135R Stratotanker |
| `rq170.svg` | `rq170` · RQ-170 Sentinel |
| `mq9.svg` | `mq9` · MQ-9A Reaper |
| `lucas.svg` | `lucas` · Dron de ataque de un solo uso (tipo LUCAS) |
| `mh47g.svg` | `mh47g` · MH-47G Chinook (160.º SOAR) |
| `mh60m.svg` | `mh60m` · MH-60M Black Hawk (160.º SOAR) |
| `mh60dap.svg` | `mh60dap` · MH-60M DAP (Direct Action Penetrator) |
| `ah6m.svg` | `ah6m` · AH-6M Little Bird (160.º SOAR) |
| `mh6m.svg` | `mh6m` · MH-6M Little Bird (160.º SOAR) |
