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
| `zu23_2.svg` | `zu23_2` · ZU-23-2 (sección de 2 montajes), de la miniatura 3D del simulador |
| `pechora_2m.svg` | `pechora_2m` · S-125 Pechora-2M (batería), de la miniatura 3D del simulador |
| `buk_m2e.svg` | `buk_m2e` · Buk-M2E (batería), de la miniatura 3D del simulador |
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
| `ref_zu23_2.jpg` | `zu23_2` · Canon antiaereo ZU-23-2 | ZU-23-2 in Saint Petersburg | One half 3544 | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:ZU-23-2_in_Saint_Petersburg.jpg |
| `ref_pechora_2m.jpg` | `pechora_2m` · S-125 Pechora-2M | Pechora-2M - missile launcher 1 | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Pechora-2M_-_missile_launcher_1.jpg |
| `ref_buk_m2e.jpg` | `buk_m2e` · Buk-M2E | BUK-M2E VEN | Cancillería del Ecuador | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0) | https://commons.wikimedia.org/wiki/File:BUK-M2E_VEN.jpg |
| `ref_s300vm.jpg` | `s300vm` · S-300VM Antey-2500 | 9A83ME TEL - Antey-2500 SAM 02 | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:9A83ME_TEL_-_Antey-2500_SAM_02.jpg |
| `ref_infanteria.jpg` | `infanteria` · Infanteria | 103-vdv-vitebsk-02 | Serge Serebro, Vitebsk Popular News | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:103-vdv-vitebsk-02.jpg |
| `ref_blindado.jpg` | `blindado` · Tanque | T-72B1 2 | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:T-72B1_2.jpg |
| `ref_artilleria.jpg` | `artilleria` · Artilleria autopropulsada | SPG 2S19M2 "Msta-S" on "Oboronexpo" in 2014 (front view) | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:SPG_2S19M2_%22Msta-S%22_on_%22Oboronexpo%22_in_2014_(front_view).jpg |
| `ref_reconocimiento.jpg` | `reconocimiento` · Vehiculo de reconocimiento | BRDM-2 (1964) owned by James Stewart pic6 | AlfvanBeem | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) | https://commons.wikimedia.org/wiki/File:BRDM-2_(1964)_owned_by_James_Stewart_pic6.JPG |
| `ref_ingenieros.jpg` | `ingenieros` · Ingenieros de combate | IMR engineering vehicle ( Military-historical Museum of Artillery, Engineer and Signal Corps) | Anna Chernichko from St. Petersburg, Russia | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0) | https://commons.wikimedia.org/wiki/File:IMR_engineering_vehicle_(_Military-historical_Museum_of_Artillery,_Engineer_and_Signal_Corps).jpg |
| `ref_transporte.jpg` | `transporte` · Convoy logistico | TB2015ExhibitionP1-58 | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:TB2015ExhibitionP1-58.jpg |
| `ref_lanzador_misiles.jpg` | `lanzador_misiles` · Lanzacohetes | Caracas, Canciller Ricardo Patiño participó en los actos de conmemoración de la muerte de Hugo Chávez (12960876943) | Cancillería del Ecuador from Ecuador | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0) | https://commons.wikimedia.org/wiki/File:Caracas,_Canciller_Ricardo_Pati%C3%B1o_particip%C3%B3_en_los_actos_de_conmemoraci%C3%B3n_de_la_muerte_de_Hugo_Ch%C3%A1vez_(12960876943).jpg |
| `ref_radar.jpg` | `radar` · Radar de vigilancia | P-18PL radar | Unknown authorUnknown author | [CC BY 3.0 pl](https://creativecommons.org/licenses/by/3.0/pl/deed.en) | https://commons.wikimedia.org/wiki/File:P-18PL_radar.png |
| `ref_guerra_electronica.jpg` | `guerra_electronica` · Guerra electronica | Electronic Warfare Vehicle Provides Signal Intelligence for Sky Soldiers (4738453) | U.S. Army 173IBCT-A by Capt. Joe Legros | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:Electronic_Warfare_Vehicle_Provides_Signal_Intelligence_for_Sky_Soldiers_(4738453).jpg |
| `ref_antiaerea_portatil.jpg` | `antiaerea_portatil` · Antiaerea portatil | 9K338 Igla-S (NATO-Code - SA-24 Grinch) | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:9K338_Igla-S_(NATO-Code_-_SA-24_Grinch).jpg |
| `ref_pechora_2m.jpg` | `antiaerea` · Antiaerea | Pechora-2M - missile launcher 1 | Vitaly V. Kuzmin | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Pechora-2M_-_missile_launcher_1.jpg |
| `ref_zu23_2.jpg` | `artilleria_antiaerea` · Artilleria antiaerea | ZU-23-2 in Saint Petersburg | One half 3544 | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:ZU-23-2_in_Saint_Petersburg.jpg |
| `ref_mistral.jpg` | `mistral` · Misil Mistral | Mistral Atlas launcher of the Hungarian Armed Forces cropped | Admiralis-generalis-Aladeen | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) | https://commons.wikimedia.org/wiki/File:Mistral_Atlas_launcher_of_the_Hungarian_Armed_Forces_cropped.jpg |
| `ref_rbs70.jpg` | `rbs70` · RBS 70 | RBS 70 (3) | Reise Reise | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:RBS_70_(3).jpg |
| `ref_f22.jpg` | `f22` · F-22A Raptor | F-22 Raptor edit1 | F-22_Raptor.JPG: Master Sgt. Andy Dunaway | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:F-22_Raptor_edit1.jpg |
| `ref_f35a.jpg` | `f35a` · F-35A Lightning II | F-35 Heritage Flight Team performs in Bell Fort Worth Alliance AirShow | Airman 1st Class Alexander Cook | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:F-35_Heritage_Flight_Team_performs_in_Bell_Fort_Worth_Alliance_AirShow.jpg |
| `ref_f35b.jpg` | `f35b` · F-35B Lightning II | Royal Air Force Lockheed Martin F-35B Lightning II ZM166 032 Royal International Air Tattoo 2025 02 | Julian Herzog (Website) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) | https://commons.wikimedia.org/wiki/File:Royal_Air_Force_Lockheed_Martin_F-35B_Lightning_II_ZM166_032_Royal_International_Air_Tattoo_2025_02.jpg |
| `ref_fa18ef.jpg` | `fa18ef` · F/A-18E/F Super Hornet | Boeing FA-18F Super Hornet at take off Danish Air Show 2014-06-22 aligned | Slaunger | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:Boeing_FA-18F_Super_Hornet_at_take_off_Danish_Air_Show_2014-06-22_aligned.jpg |
| `ref_ea18g.jpg` | `ea18g` · EA-18G Growler | Boeing EA-18G Growler of VAQ-141 in flight on 24 March 2012 | ぽりたんく | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:Boeing_EA-18G_Growler_of_VAQ-141_in_flight_on_24_March_2012.jpg |
| `ref_b1b.jpg` | `b1b` · B-1B Lancer | A B-1B Lancer | Master Sgt. Nicholas Priest | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:A_B-1B_Lancer.jpg |
| `ref_p8a.jpg` | `p8a` · P-8A Poseidon | P-8A Poseidon Executes Training Flight (9341127) | U.S. Navy photo by Lt. Sara Wedemeyer | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:P-8A_Poseidon_Executes_Training_Flight_(9341127).jpg |
| `ref_e2d.jpg` | `e2d` · E-2D Advanced Hawkeye | E-2D Advanced Hawkeye aircraft conduct a test flight | US Navy | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:E-2D_Advanced_Hawkeye_aircraft_conduct_a_test_flight.jpg |
| `ref_e3g.jpg` | `e3g` · E-3G Sentry (AWACS) | E-3 Sentry Airborne Warning and Control System (AWACS) conducts a mission | Senior Airman Roslyn Ward | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:E-3_Sentry_Airborne_Warning_and_Control_System_(AWACS)_conducts_a_mission.jpg |
| `ref_rc135.jpg` | `rc135` · RC-135V/W Rivet Joint | 20190206 RC-135 Rivet Joint Kadena AB-25 | Balon Greyjoy | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) | https://commons.wikimedia.org/wiki/File:20190206_RC-135_Rivet_Joint_Kadena_AB-25.jpg |
| `ref_ec130h.jpg` | `ec130h` · EC-130H Compass Call | EC-130H Compass Call 060617 | Mil | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:EC-130H_Compass_Call_060617.jpg |
| `ref_kc135.jpg` | `kc135` · KC-135R Stratotanker | 931st Air Refueling Group - Boeing KC-135R-BN Stratotanker 60-0336 | United States Air Force | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:931st_Air_Refueling_Group_-_Boeing_KC-135R-BN_Stratotanker_60-0336.jpg |
| `ref_rq170.jpg` | `rq170` · RQ-170 Sentinel | RQ-170 Wiki contributor 3Dartist | Truthdowser | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) | https://commons.wikimedia.org/wiki/File:RQ-170_Wiki_contributor_3Dartist.png |
| `ref_mq9.jpg` | `mq9` · MQ-9A Reaper | MQ-9 Reaper in flight 2 | Desconocido | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:MQ-9_Reaper_in_flight_2.jpg |
| `ref_lucas.jpg` | `lucas` · Dron de ataque de un solo uso (tipo LUCAS) | LUCAS the American reverse-engineered version of the Shahed-136 one-way attack drone | Cpl. Kayla Mc Guire | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:LUCAS_the_American_reverse-engineered_version_of_the_Shahed-136_one-way_attack_drone.jpg |
| `ref_mh47g.jpg` | `mh47g` · MH-47G Chinook | Special Boat Team takes flight with Nightstalkers 140521-A-PP158-057 | Sgt. Christopher Prows | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:Special_Boat_Team_takes_flight_with_Nightstalkers_140521-A-PP158-057.jpg |
| `ref_mh60m.jpg` | `mh60m` · MH-60M Black Hawk | Sikorsky UH-60 Black Hawk - 04 | Oleg Yunakov | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) | https://commons.wikimedia.org/wiki/File:Sikorsky_UH-60_Black_Hawk_-_04.jpg |
| `ref_mh60dap.jpg` | `mh60dap` · MH-60M DAP | MH-60M DAP firing 2.75 inch rockets at a test ground | U.S. Army | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:MH-60M_DAP_firing_2.75_inch_rockets_at_a_test_ground.jpg |
| `ref_ah6m.jpg` | `ah6m` · AH-6M Little Bird | 2 AH-6J Little Bird de l'US Army, 31 mars 2003, Irak | Desconocido | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:2_AH-6J_Little_Bird_de_l%27US_Army,_31_mars_2003,_Irak.jpg |
| `ref_mh6m.jpg` | `mh6m` · MH-6M Little Bird | US Army 160th SOAR MH-6 | U.S. Army | [Public domain](https://commons.wikimedia.org/wiki/Commons:Licensing) | https://commons.wikimedia.org/wiki/File:US_Army_160th_SOAR_MH-6.jpg |
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
| `s300vm.svg` | `s300vm` · S-300VM Antey-2500 (batería) |
| `mistral.svg` | `mistral` · Mistral (sección de 4 puestos) |
| `rbs70.svg` | `rbs70` · RBS 70 (sección con radar Giraffe) |
