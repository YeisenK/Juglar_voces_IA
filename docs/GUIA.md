# Guía de Juglar

Cómo escribir tus textos para que Juglar los lea lo mejor posible, y qué voces tienes para narrar y para los personajes.

---

## 1. Cómo funciona, en una frase

Un **narrador** lee todo el texto. Cuando un párrafo empieza con **raya (—)**, ese párrafo es un diálogo y lo lee **la voz del personaje** que indiques al principio. Lo que no es diálogo lo sigue leyendo el narrador.

---

## 2. Cómo escribir

### 2.1 Estructura del documento (Markdown)

| Escribes | Lo que hace Juglar |
|---|---|
| `# Capítulo uno` | Lo lee como título, con pausa antes y después, y crea un **capítulo** en el audio (útil en `.m4b`). |
| `## Escena dos` | Igual, un subtítulo. |
| Una línea en blanco entre párrafos | Pausa de párrafo. **Separa siempre los párrafos con una línea en blanco.** |
| `---` o `***` solo en una línea | **Cambio de escena**: una pausa larga (2 s por defecto). |
| `**negrita**`, `*cursiva*` | Se leen normal; los asteriscos no se pronuncian. |
| `[texto](enlace)` | Lee solo «texto». |
| Bloques de código entre ``` | No se leen. |
| `- elemento` (listas) | Cada elemento se lee como una frase. |

### 2.2 Diálogos: la parte más importante

Usa siempre la **raya larga «—»**, no el guion corto «-». Si tu teclado no la tiene, cópiala de aquí: **—**

Hay tres formas de decir quién habla. La marca va **justo después de la raya, al principio del párrafo**, y **no se lee en voz alta**:

| Escribes | Quién lo lee |
|---|---|
| `—@leonor ¿Tienes miedo?` | El **personaje con nombre** Leonor (ver sección 3.2). Es la forma recomendada. |
| `—Leonor: ¿Tienes miedo?` | Lo mismo, si el personaje existe. |
| `—2 Solo queda la del fondo.` | La **voz número 2** (se asigna en la pestaña *Voces*). |
| `—¿Hay alguien ahí?` (sin marca) | La **voz de los diálogos** elegida en la pestaña *Audiolibro* (por defecto, el mismo narrador). |

**Acotaciones** (el «dijo Marta» entre rayas):

```
—@marta ¿Tiene una habitación? —preguntó Marta—. Vengo de muy lejos.
```

- Las acotaciones **cortas** («preguntó Marta», «dijo él») las dice la misma voz del personaje, para no cortar la frase.
- Las acotaciones **largas** («—El ojo se movió hacia la hondonada, hacia las cabras—») las lee el **narrador**.

**Reglas que conviene respetar**

1. **Un personaje por párrafo.** Si habla otro, empieza un párrafo nuevo con su raya y su marca.
2. La marca solo cuenta **al inicio del párrafo**.
3. Si escribes `—@alguien` y ese personaje no existe, la marca no se lee y en el panel *Propiedades* aparece el aviso «no existe: créalo en Voces».
4. Los diálogos entre comillas («así» o "así") **no** cambian de voz: los lee el narrador.

### 2.3 Números, fechas y abreviaturas

Juglar los convierte a palabras solo. No hace falta escribirlos en letra:

| Escribes | Se lee |
|---|---|
| `21 años`, `1 casa`, `31 casas` | veintiún años, una casa, treinta y una casas |
| `1.250.000`, `3,5` | un millón doscientos cincuenta mil, tres coma cinco |
| `12/03/1998` | doce de marzo de mil novecientos noventa y ocho |
| `10:30` | diez treinta |
| `3.º`, `2.ª`, `1.er` | tercero, segunda, primer |
| `Capítulo XII`, `siglo XIX` | Capítulo doce, siglo diecinueve |
| `Felipe II`, `Luis XIV` | Felipe segundo, Luis catorce |
| `Sr.`, `Dra.`, `EE. UU.`, `etc.` | señor, doctora, Estados Unidos, etcétera |
| `5 km`, `1 kg`, `20 °C`, `15%` | cinco kilómetros, un kilogramo, veinte grados centígrados, quince por ciento |

Lo que **no** convierte (escríbelo en letra si importa):

- El símbolo `$` (no sabe si son pesos o dólares).
- Números romanos sueltos sin una palabra antes que los explique (`la fila IV`).

### 2.4 Pronunciación de nombres raros

Si una voz pronuncia mal un nombre inventado o extranjero, añádelo al **diccionario de pronunciación** (pestaña *Audiolibro* → botón *Diccionario de pronunciación*). Una línea por palabra:

```
Hermione = Jermáyoni
Edward = Édguard
NASA = Nasa
```

Distingue mayúsculas y solo cambia palabras completas.

### 2.5 Consejos para que suene natural

- **Usa la puntuación completa**: `¿…?` y `¡…!` con los dos signos. La voz entona según ellos.
- **Puntos suspensivos** (`...` o `…`) dan una pausa dubitativa. Úsalos cuando el personaje duda.
- **Evita PALABRAS ENTERAS EN MAYÚSCULAS**: a veces las deletrea. Para un grito, usa `¡…!`.
- **Párrafos de longitud normal.** Los muy largos se parten solos, pero un párrafo de 2–6 frases suena mejor.
- **No uses emojis ni símbolos decorativos** (★, →, ♥): se ignoran o se leen raro.
- **Revisa el panel *Propiedades*** (pestaña *Leer*, a la derecha) antes de exportar: muestra qué voz tiene cada marca del texto y avisa de personajes que no existen.

---

## 3. Voces que puedes usar

### 3.1 Voces de Qwen (las de mejor calidad)

Se eligen como **narrador** (desplegable *Voz*) o se asignan a un **número** (`—1` … `—5`) en la pestaña *Voces*.

Cada voz es también un personaje: se escribe con `—@` y su nombre (`—@mujer_joven`, `—@tabernero`). En la pestaña *Voces* puedes cambiarle el **nombre**, y su marca pasa a ser ese nombre (`Mozo de pueblo` → `—@mozo_de_pueblo`); la marca con el nombre de la carpeta sigue valiendo. El botón de copiar te da la marca lista para pegar.

**Narradores**

| Voz en la app | Cómo suena |
|---|---|
| Narradora de audiolibros | Mujer ~30, cálida, suave, latina neutra. Pausada y expresiva. |
| Narrador de audiolibros | Hombre ~40, grave, cálido y resonante, latino neutro. |
| Narradora española | Mujer ~35, acento de España, cálida y clara. |
| Narradora de documentales | Mujer ~45, serena, profunda y elegante. |
| Narrador de documentales | Hombre ~55, profundo, sereno, solemne. |

**Voces para personajes** — todas en español nativo, con un tono normal de conversación, sin dramatizar.
Si una voz se renombra en la app, también se puede escribir con su nombre (`—@hombre_viejo` = *Hombre viejo*).

*Hombres*

| Escribe | Voz en la app | Cómo suena |
|---|---|---|
| `—@hombre_joven` | Hombre joven | Hombre joven ~25. Timbre medio, claro y agradable. Tono amable y sencillo. |
| `—@hombre_joven_alegre` | Hombre joven alegre | Hombre joven ~24. Timbre claro y luminoso. Tono alegre y simpático, con una sonrisa ligera en la voz. |
| `—@hombre_joven_timido` | Hombre joven tímido | Hombre joven ~22. Timbre suave, de altura media. Tono tímido y algo inseguro, volumen bajo. |
| `—@hombre_joven_serio` | Hombre joven serio | Hombre joven ~27. Timbre firme y limpio. Tono serio y formal, ritmo pausado. |
| `—@hombre_joven_grunon` | Hombre joven gruñón | Hombre joven ~25. Timbre medio tirando a grave. Tono algo seco y malhumorado, de pocas palabras, pero sin gritar. |
| `—@hombre_adulto` | Hombre adulto | Hombre adulto ~40. Timbre grave y claro. Tono tranquilo y normal. |
| `—@hombre_adulto_amable` | Hombre adulto amable | Hombre adulto ~45. Timbre cálido y grave. Tono amable y paciente. |
| `—@hombre_adulto_serio` | Hombre adulto serio | Hombre adulto ~50. Timbre grave y firme. Tono serio y sobrio, de pocas palabras. |
| `—@hombre_grunon` | Hombre gruñón | Hombre adulto ~45. Timbre grave, algo áspero. Tono seco y gruñón, impaciente, pero sin gritar. |
| `—@anciano` | Hombre viejo | Hombre mayor ~75. Timbre grave, algo gastado. Tono sereno y normal, ritmo pausado. |
| `—@hombre_viejo_alegre` | Hombre viejo alegre | Hombre mayor ~72. Timbre cálido y algo gastado. Tono alegre y bonachón, de abuelo contento. |
| `—@hombre_viejo_grunon` | Hombre viejo gruñón | Hombre mayor ~75. Timbre ronco y gastado. Tono gruñón y quejumbroso, de viejo cascarrabias, sin gritar. |
| `—@pastor_viejo` | Pastor viejo | Hombre mayor ~75, pastor de montaña. Timbre suave y gastado. Tono tranquilo y sencillo, habla despacio. |

*Mujeres*

| Escribe | Voz en la app | Cómo suena |
|---|---|---|
| `—@mujer_joven` | Mujer joven | Mujer joven ~25. Timbre medio, claro y agradable. Tono amable y sencillo. |
| `—@mujer_joven_alegre` | Mujer joven alegre | Mujer joven ~23. Timbre claro y luminoso. Tono alegre y simpático, con una sonrisa ligera en la voz. |
| `—@mujer_joven_timida` | Mujer joven tímida | Mujer joven ~21. Timbre suave. Tono tímido y algo inseguro, volumen bajo. |
| `—@mujer_joven_seria` | Mujer joven seria | Mujer joven ~27. Timbre medio tirando a grave, firme. Tono serio y formal, ritmo pausado. |
| `—@mujer_joven_grunona` | Mujer joven gruñona | Mujer joven ~25. Timbre medio. Tono seco y malhumorado, de pocas palabras, pero sin gritar. |
| `—@mujer_adulta` | Mujer adulta | Mujer adulta ~40. Timbre medio y claro. Tono tranquilo y normal. |
| `—@mujer_adulta_amable` | Mujer adulta amable | Mujer adulta ~45. Timbre cálido. Tono amable y maternal. |
| `—@mujer_adulta_severa` | Mujer adulta severa | Mujer adulta ~50. Timbre firme, algo grave. Tono severo y exigente, sin levantar la voz. |
| `—@mujer_misteriosa` | Mujer misteriosa | Mujer adulta ~40. Timbre grave y suave. Tono reservado y enigmático, habla bajo y despacio. |
| `—@anciana` | Mujer vieja | Mujer mayor ~75. Timbre suave, algo gastado. Tono sereno y normal, ritmo pausado. |
| `—@mujer_vieja_alegre` | Mujer vieja alegre | Mujer mayor ~72. Timbre cálido. Tono alegre y cariñoso, de abuela contenta. |
| `—@mujer_vieja_grunona` | Mujer vieja gruñona | Mujer mayor ~75. Timbre algo áspero. Tono gruñón y quejumbroso, de vieja cascarrabias, sin gritar. |
| `—@vieja_brava` | Vieja de pueblo (brava) | Mujer mayor de pueblo ~70. Timbre grave y fuerte. Tono mandón y directo, sin gritar. |
| `—@vieja_chismosa` | Vieja chismosa | Mujer mayor de pueblo ~70. Timbre algo agudo. Tono curioso y confidencial, de quien cuenta un chisme. |
| `—@partera_vieja` | Partera vieja | Mujer mayor ~70, partera de pueblo. Timbre firme. Tono práctico y seguro, sin rodeos. |

*Niños y adolescentes*

| Escribe | Voz en la app | Cómo suena |
|---|---|---|
| `—@nino` | Niño | Niño ~9. Timbre agudo e infantil. Tono curioso y normal. |
| `—@nina` | Niña | Niña ~9. Timbre agudo e infantil. Tono dulce y normal. |
| `—@adolescente_chico` | Adolescente (chico) | Chico adolescente ~15, voz que está cambiando. Tono normal, algo despreocupado. |
| `—@adolescente_chica` | Adolescente (chica) | Chica adolescente ~15. Timbre claro. Tono normal, algo despreocupado. |
| `—@mozo_pueblo` | Mozo de pueblo | Muchacho de pueblo ~17. Timbre juvenil. Tono sencillo y servicial. |

*Oficios y gente del reino*

| Escribe | Voz en la app | Cómo suena |
|---|---|---|
| `—@guerrero` | Guerrero | Hombre ~35, soldado veterano. Timbre grave y firme. Tono seguro y directo, sin gritar. |
| `—@soldado_joven` | Soldado joven | Hombre joven ~20, soldado raso. Timbre medio. Tono disciplinado y algo nervioso. |
| `—@capitan` | Capitán | Hombre ~45, capitán de soldados. Timbre grave y firme. Tono de mando tranquilo y seguro. |
| `—@guardia` | Guardia | Hombre ~35, guardia de una puerta. Timbre grave. Tono aburrido y desconfiado. |
| `—@caballerizo` | Caballerizo | Hombre ~30, mozo de cuadras que cuida caballos. Timbre medio y cálido. Tono sencillo y tranquilo. |
| `—@herrero` | Herrero | Hombre ~45, herrero. Timbre muy grave y potente. Tono campechano y franco. |
| `—@tabernero` | Tabernero | Hombre ~50, tabernero. Timbre grave y algo ronco. Tono campechano y hospitalario. |
| `—@tabernera` | Tabernera | Mujer ~40, tabernera. Timbre medio y firme. Tono despierto y hospitalario. |
| `—@campesino` | Campesino | Hombre ~50, campesino. Timbre gastado y cálido. Tono humilde y sencillo, habla despacio. |
| `—@campesina` | Campesina | Mujer ~40, campesina. Timbre claro y firme. Tono sencillo y práctico. |
| `—@mercader` | Mercader | Hombre ~45, mercader. Timbre medio y agradable. Tono cortés y persuasivo. |
| `—@fraile` | Fraile | Hombre ~55, fraile. Timbre suave y grave. Tono sereno y bondadoso, habla despacio. |
| `—@criado` | Criado | Hombre ~30, criado de una casa noble. Timbre medio. Tono discreto y respetuoso. |
| `—@criada` | Criada | Mujer ~25, criada de una casa noble. Timbre suave. Tono discreto y respetuoso. |
| `—@mensajero` | Mensajero | Hombre joven ~22, mensajero. Timbre claro. Tono rápido y apurado, pero claro. |
| `—@cocinera` | Cocinera | Mujer ~50, cocinera. Timbre cálido y firme. Tono práctico y bonachón. |
| `—@noble` | Noble | Hombre ~50, señor noble. Timbre grave y cuidado. Tono educado y seguro. |
| `—@dama_noble` | Dama noble | Mujer ~40, dama noble. Timbre suave y cuidado. Tono educado y sereno. |
| `—@rey` | Rey | Hombre ~55, rey. Timbre grave y sereno. Tono de autoridad tranquila. |
| `—@reina` | Reina | Mujer ~45, reina. Timbre firme y elegante. Tono de autoridad tranquila. |
| `—@villano` | Villano | Hombre ~50. Timbre grave y frío. Tono calmado y amenazante, habla bajo. |

*Acentos*

| Escribe | Voz en la app | Cómo suena |
|---|---|---|
| `—@hombre_argentino` | Hombre (Argentina) | Hombre ~35. Timbre medio y agradable. Tono normal. |
| `—@hombre_espana` | Hombre (España) | Hombre ~40. Timbre medio y claro. Tono normal. |
| `—@mujer_mexicana` | Mujer (México) | Mujer ~30. Timbre claro y cálido. Tono normal. |

### 3.2 Personajes con nombre (para tu libro)

Cada uno tiene **su propia voz**, creada a partir de la descripción que me diste. Se escriben con `—@nombre`:

| Escribe | Personaje | Cómo suena |
|---|---|---|
| `—@cid` | Cid | ~35, barítono firme y limpio, arrogante y seguro, cortante al mandar, nunca duda. |
| `—@cid_version_2` | Cid (versión 2) | Otra toma: ~30, barítono brillante, burlón y salvaje. Quédate con la que prefieras. |
| `—@dona_huma` | Doña Huma | ~65, de origen árabe o persa: habla un español excelente con un ligero acento; suave, irónica, nunca levanta la voz. |
| `—@galindo` | Galindo | ~85, ronca y temblorosa, viejo soldado gruñón («¡mal rayo!»). |
| `—@pedro` | Pedro | ~40, grave y opaca, de artesano, pocas palabras, tristeza contenida. |
| `—@bermudo` | Bermudo | ~45, tenor grave, culto, amable, algo melancólico. |
| `—@arnau` | Arnau | ~50, sargento ronco y fuerte, malhablado, acento de costa. |
| `—@tri` | Tri | ~22, claro y cálido, curioso; se atropella cuando se entusiasma y duda con pausas cortas. |
| `—@tri_falso` | Tri falso | La misma voz de Tri, pero lisa y uniforme, sin dudas: tranquila e inquietante por lo perfecta. |
| `—@leonor` | Leonor | ~25, mujer joven de timbre vivo y brillante: práctica y directa, burlona con confianza, rápida cuando está nerviosa y cálida cuando es tierna. |
| `—@myria` | Myria | ~22, noble: suave y aterciopelada, lenta y contenida, melancólica. |
| `—@luca` | Luca | ~35, heredero: barítono cálido y cansado, risa nerviosa por la nariz, seco cuando hay tensión. |
| `—@maia` | Maia | ~30, la hermana mayor: curiosa y mandona, lo pregunta todo y organiza a todos; cálida y firme. |
| `—@maximo` | Máximo | ~60, emperador: bajo profundo y lento, pocas palabras; a ratos eufórico, ríe fuerte. |
| `—@helena` | Helena | ~55, emperatriz: contralto cálida y algo susurrante, maternal, frases cortas cuando algo importa. |
| `—@gaia` | Gaia | ~21, enérgica, algo ronca, franca y de risa fácil; le cuesta ser formal. |
| `—@seranith` | Seraníth | Sin edad: mezzo clara y fría, dicción formal y precisa, orgullo de guerrera. |
| `—@aelia` | Aelia | Casi dos mil años: grave, etérea, muy lenta y casi susurrada, cadencia poética. |
| `—@celso_maran` | Celso Marán | ~60, jefe de espías: seca, neutra y olvidable, como quien lee un informe. |
| `—@remo_armen` | Remo Armen | ~55, mitad oso: bajo enorme como un trueno, pero muy amable, un gigante bonachón. |
| `—@micael` | Micael | ~28, capitán: firme y serio, frases cortas, valor tranquilo. |

Puedes cambiar la temperatura y la velocidad de cada personaje en la pestaña **Voces** (aparecen arriba de la lista, bajo «Personajes»). Los cambios no se aplican hasta que pulsas **Guardar** (`Ctrl+S`), que se ilumina en azul cuando hay algo sin guardar; **Probar** ya suena con lo que estás tocando. Con **Borrar…** se manda una voz a la papelera.

### 3.3 Voces rápidas (Piper y Kokoro)

Suenan menos naturales pero empiezan a leer al momento. Útiles para escuchar un texto rápido en la pestaña *Leer*; para audiolibros usa Qwen.

---

## 4. Ejemplo completo

```markdown
# Capítulo uno: La posada

La posada estaba casi vacía cuando Leonor entró, empapada de lluvia, y dejó el paraguas junto a la chimenea.

—@leonor ¿Tiene una habitación para esta noche? —preguntó—. Vengo de muy lejos.

—@pedro Solo queda la del fondo.

El posadero no levantó la vista de la jarra que estaba secando. Afuera, el viento golpeaba los postigos como si alguien quisiera entrar.

—@galindo ¡Mal rayo! Nadie duerme bien en esa habitación, muchacha. Yo lo sé.

---

A la mañana siguiente, el camino del norte estaba cubierto de nieve.
```

Qué pasará al leerlo:

- El título se lee como capítulo, con pausa.
- El narrador lee los párrafos sin raya.
- Leonor, Pedro y Galindo hablan con sus voces; las acotaciones («preguntó», «dijo Galindo») las lee siempre el narrador.
- `---` deja una pausa larga de cambio de escena.

---

## 5. Flujo de trabajo recomendado

1. **Escribe** tu capítulo en un `.md` con las marcas de diálogo.
2. Ábrelo en la pestaña **Leer** (`Ctrl+O`) y mira el panel **Propiedades**: comprueba el reparto. Una marca que no existe sale en naranja con sus líneas («no existe (líneas 3, 5)»), y al exportar Juglar te avisa con el archivo y la línea de cada una antes de empezar.
3. Escucha un trozo con **Leer** (`Ctrl+Intro` para leer/pausar, `Esc` para detener).
4. Cuando te guste, pulsa **Exportar a audio…** (`Ctrl+Mayús+E`) o añade el archivo en la pestaña **Exportar**. Se convierte en segundo plano, aunque cierres la ventana.
5. Para audiolibros largos, deja activado **Revisar con Whisper** (pestaña *Audiolibro*): escucha cada fragmento y regenera los que salgan mal.
6. ¿Prisa? Activa **⚡ Modo flash** (arriba en la pestaña *Audiolibro*): no se revisa con Whisper y todo lo lee el narrador; las marcas `—2` y `—@leonor` se quitan y no se leen. También desde la terminal: `md2audio libro.md --flash`.

7. ¿Un libro entero? Pon los capítulos en una carpeta y usa **Exportar carpeta…** (sección 6).
8. ¿Una frase salió mal en el audio? No hace falta rehacer el capítulo: **Rehacer un trozo** (sección 7).

### Atajos

| Atajo | Acción |
|---|---|
| `Ctrl+Intro` | Leer / pausar |
| `Esc` | Detener |
| `Ctrl+O` | Abrir y leer un archivo |
| `Ctrl+Mayús+E` | Exportar el texto a audio |
| `Ctrl+1` … `Ctrl+4` | Leer · Exportar · Voces · Audiolibro |

## 6. Libros por carpetas

Un libro es **una carpeta**, y cada archivo `.md` o `.txt` dentro de ella es **un capítulo**:

```
Cid el conquistador/
├── juglar.json                  (opcional) ajustes del libro
├── Cid_C1_El_bravo.md           capítulos
├── Cid_C2_La_sala_grande.md
├── …
├── Cid_C10_El_rio.md
├── _notas.md                    lo que empieza por «_» o «.» no se lee
└── audio/                       aquí deja Juglar los audios
    ├── Cid_C1_El_bravo.mp3
    └── …
```

**Cómo exportarlo**: en la pestaña **Exportar**, pulsa **Exportar carpeta…** y elige la carpeta (o arrástrala a la cola). Juglar:

1. Busca los capítulos y los **ordena por su nombre en orden natural**: `C2` va antes que `C10`, y `01 …`, `02 …` también funcionan. Para controlar el orden, empieza los nombres con un número.
2. **Comprueba las marcas** de todo el libro y, si alguna `—@marca` no existe, te dice en qué archivo y línea está.
3. Si algunos capítulos **ya tienen audio** en `audio/`, te pregunta si exportar **solo los que faltan** o **todos de nuevo**.
4. Los añade a la cola **en orden**, con el nombre del libro («Cid el conquistador · Cid_C1_El_bravo»).

Desde la terminal hace lo mismo: `juglar-cola libro "Cid el conquistador"` (con `--todo` vuelve a exportar también los que ya tienen audio).

### `juglar.json`: los ajustes del libro (opcional)

Sin este archivo se usan el narrador, el formato y la velocidad elegidos en la app. Con él, cada libro recuerda los suyos:

```json
{
  "titulo": "Cid el conquistador",
  "narrador": "narrador",
  "formato": "mp3",
  "velocidad": 1.0,
  "carpeta_audio": "audio",
  "omitir": ["Cid_C0_borrador.md"]
}
```

| Clave | Qué es | Por defecto |
|---|---|---|
| `titulo` | Nombre del libro en la cola | El de la carpeta |
| `narrador` | Voz que narra: el nombre de una voz de Qwen (`narrador`, `narradora`…) o el nombre completo (`qwen:narrador`, `es_MX-claude-high`) | La elegida en la app |
| `formato` | `mp3`, `ogg`, `m4b` (audiolibro con capítulos) o `wav` | El elegido en la app |
| `velocidad` | 1.0 normal, 1.1 algo más rápido | La elegida en la app |
| `carpeta_audio` | Dónde se guardan los audios, relativo al libro. `"."` los deja junto a cada capítulo | `audio` |
| `omitir` | Capítulos que no se exportan (con o sin extensión) | Ninguno |

Todas las claves son opcionales: `{"narrador": "narradora"}` ya es un `juglar.json` válido.

## 7. Rehacer un trozo de un audio

Si al escuchar un capítulo exportado una frase salió mal (una palabra mal dicha, un tono raro), **no hace falta volver a exportar el capítulo entero**:

1. En la pestaña **Exportar**, en la fila del audio, pulsa el botón del lápiz (**Rehacer un trozo**).
2. Sale la lista de fragmentos del audio, con su minuto y su voz. Busca la frase con el buscador y escúchala con ▶.
3. Pulsa **Rehacer…**. Puedes **corregir el texto** antes (por ejemplo, escribir «Édguard» para que pronuncie bien «Edward»).
4. Se añade a la cola: se genera solo ese trozo, **con la misma voz y los mismos ajustes** con que se exportó, se revisa con Whisper si está activado y se cambia en el audio. Lo demás no se toca, y los capítulos (`m4b`) se recolocan solos si el trozo dura más o menos.

### Corregiste el texto: cargar el .md nuevo

Si cambiaste varias cosas en el capítulo (frases corregidas, un párrafo nuevo, otro que sobraba), no hace falta ir trozo por trozo:

1. En la ventana de **Rehacer un trozo**, pulsa **Cargar .md corregido…** y elige el archivo. Si el `.md` con que se exportó cambió después, también aparece el botón **Usar «capítulo.md»**.
2. Juglar trocea el texto nuevo igual que al exportar y lo compara con lo que se oye en el audio. Te enseña cada cambio con **lo que había** (en rojo y tachado) y **lo que hay ahora** (en verde), el minuto donde está y un ▶ para escuchar cómo suena ahora.
3. Pulsa **Rehacer N trozos**: en la cola se generan solo los trozos que cambiaron o son nuevos, se quitan los que borraste y el resto del audio se queda igual. Los capítulos se recolocan solos.

Ojo: si después de exportar cambiaste los ajustes del audiolibro (por ejemplo, el tamaño de los fragmentos o la voz de los diálogos), el texto se trocea distinto y saldrán más cambios de los que hiciste.

Para que esto funcione, Juglar guarda junto a cada audio un archivo oculto con el mapa de sus fragmentos (`.Capítulo.mp3.juglar.json`). Si lo borras, el audio sigue funcionando, pero ya no se puede rehacer por trozos. Los audios exportados antes de esta función no lo tienen: vuelve a exportarlos una vez.

Desde la terminal:

```bash
md2audio audio/Cid_C1_El_bravo.mp3 --fragmentos          # lista: número, minuto, voz y texto
juglar-cola rehacer audio/Cid_C1_El_bravo.mp3 57          # rehace el fragmento 57
juglar-cola rehacer audio/Cid_C1_El_bravo.mp3 57 --texto "El texto corregido."
md2audio audio/Cid_C1_El_bravo.mp3 --comparar Cid_C1_El_bravo.md   # qué trozos cambian con el texto corregido
juglar-cola rehacer audio/Cid_C1_El_bravo.mp3 --md Cid_C1_El_bravo.md   # rehace solo esos
```

También en **Exportar** está el botón **Historial**: todos los audios que has exportado, mientras sigan en la computadora (los que borres desaparecen de la lista), con cuántos trozos se les han rehecho, para escucharlos o volver a abrir sus trozos.

## 8. Música: canciones con tu letra

La pestaña **Música** convierte en canción una letra que ya tengas escrita, con la música que describas con tus palabras. Usa [ACE-Step 1.5](https://github.com/ACE-Step/ACE-Step-1.5), un modelo libre que corre en tu tarjeta gráfica. La música es opcional: `install.sh` pregunta si la instalas (o `CON_MUSICA=1 ./install.sh`).

### 8.1 Cómo se usa

Hay dos maneras: rellenar el formulario de la pestaña, o escribir la canción en un `.md` (sección 8.2) y abrirlo o añadirlo a la cola.

**Desde la pestaña Música:**

1. **Título**: el nombre del archivo que se crea.
2. **Cómo suena**: la música descrita en lenguaje natural (estilo, instrumentos, voz, tempo, ambiente). El botón **Ejemplos** rellena algunas para empezar.
3. **Letra**: escríbela o pégala. Sin letra, sale instrumental.
4. Abajo: **duración** en segundos (0 = que la elija el modelo; hasta 8 minutos), **idioma** de la voz y **semilla** (−1 = al azar).
5. **Generar canción**: va a la misma cola que los audios (así nunca coincide con Qwen en la tarjeta) y aparece a la derecha cuando está. Se guarda en `~/Música/Juglar`.

Botones de arriba:

| Botón | Qué hace |
|---|---|
| **Abrir…** | Abre un `.md` de canción y rellena todo el formulario: título, cómo suena, duración, idioma, semilla y letra. Si el archivo solo tiene letra, carga solo la letra. También puedes arrastrar el archivo a la ventana. |
| **Guardar .md…** | Guarda lo que hay en el formulario como `.md` de canción, para generarla otra vez cuando quieras o retocarla en tu editor. |
| **Añadir .md a la cola…** | Elige uno o varios `.md` de canción y se generan directamente, sin abrirlos. Los que no digan cómo suenan no se añaden y te dice por qué. |
| **Nueva** | Vacía el formulario. |

En la lista de canciones de la derecha: ▶ escuchar, ↻ **cargar su letra, estilo y semilla** (si generas sin cambiar nada, sale la misma; cambia el estilo o pon la semilla al azar para variaciones), abrir la carpeta y mandar a la papelera. Cada canción guarda sus datos en un archivo oculto a su lado (`.Canción.mp3.musica.json`).

La primera canción tarda más porque descarga el modelo (unos 10 GB). Después, una canción de 30-40 segundos tarda unos 20-25 segundos en una tarjeta de 8 GB.

### 8.2 Reglas del `.md` de canción

Un archivo = una canción. Plantilla lista para copiar: [`docs/plantilla_cancion.md`](plantilla_cancion.md).

```markdown
# El juglar

Estilo: balada folk acústica con guitarra española, lenta e íntima
Voz: masculina, cálida
Instrumentos: guitarra, flauta, pandero
Duración: 2:30
Idioma: español
Semilla: azar

[Estrofa]
Por el camino de piedra
vuelve el juglar al anochecer

[Estribillo]
Canta, juglar, canta
que la noche es larga ya

[Puente]
…
```

Las reglas:

1. **Título**: la primera línea `# …`. Si no hay, se usa el nombre del archivo.
2. **Cabecera**: justo debajo del título, líneas `Clave: valor`, una por línea. Se pueden dejar líneas en blanco entre ellas. **La primera línea que no es una clave conocida empieza la letra**: por eso conviene empezar la letra con una etiqueta (`[Estrofa]`).
3. **Letra**: todo lo demás. Las partes se marcan entre corchetes, en español o en inglés.
4. Lo único obligatorio para generarla es **`Estilo:`** (cómo suena). Sin letra, o con `[Instrumental]` como letra, sale instrumental.

Claves de la cabecera (da igual mayúsculas o tildes):

| Clave | Qué es | Ejemplos |
|---|---|---|
| `Estilo:` (o `Descripción:`, `Cómo suena:`, `Música:`) | Cómo suena, en tus palabras. Es lo más importante. | `balada folk acústica, lenta e íntima` |
| `Voz:` | Tipo de voz que canta. Se suma al estilo. | `masculina, cálida` · `femenina, dulce y susurrada` · `coro` |
| `Instrumentos:` · `Género:` · `Ambiente:` · `Ritmo:` | Más detalles. También se suman al estilo. | `guitarra española, laúd` · `taberna medieval` |
| `> texto` | Una línea que empieza con `>` también se suma al estilo (útil para descripciones largas, en varias líneas). | `> empieza suave y crece en el estribillo` |
| `Duración:` | Cuánto dura. `auto` = la decide el modelo. Máximo 8 minutos. | `2:30` · `150` · `2 min 30 s` · `auto` |
| `Idioma:` | Idioma en que se canta. Por defecto, español. | `español` · `inglés` · `latín` · `es` |
| `Semilla:` | Número para repetir exactamente una canción. | `azar` · `1234` |
| `Tempo:` | Pulsos por minuto (si no, lo elige el modelo). | `80` · `120 bpm` |
| `Tonalidad:` | Tonalidad (si no, la elige el modelo). | `Re mayor` · `Am` · `C Major` |
| `Instrumental:` | Sin voz, aunque haya letra. | `sí` |
| `Título:` | Otra forma de poner el título. | `El juglar` |

Etiquetas de la letra:

| En español | Equivale a | Para qué |
|---|---|---|
| `[Intro]` · `[Introducción]` | `[Intro]` | Entrada, normalmente sin voz |
| `[Estrofa]` · `[Estrofa 2]` · `[Verso]` | `[Verse]` | Las estrofas |
| `[Preestribillo]` | `[Pre-Chorus]` | Lo que sube antes del estribillo |
| `[Estribillo]` · `[Coro]` | `[Chorus]` | El estribillo |
| `[Puente]` | `[Bridge]` | La parte distinta antes del último estribillo |
| `[Solo]` · `[Interludio]` · `[Instrumental]` | `[Solo]` · `[Interlude]` · `[Instrumental]` | Partes sin voz |
| `[Final]` · `[Cierre]` | `[Outro]` | El final |

Los encabezados de Markdown valen igual que los corchetes: `## Estribillo` o una línea `**Estribillo**`. Después de la etiqueta se puede añadir un detalle: `[Estribillo: todos a coro]`.

También se acepta la cabecera entre `---` al principio del archivo (como en otros programas de notas):

```markdown
---
título: Marcha de los caballeros
estilo: épica orquestal con tambores de guerra y metales
duración: 2:10
semilla: 42
---

[Instrumental]
```

### 8.3 Consejos

- **Describe en el estilo lo que oirías**, no lo que cuenta la letra: género, instrumentos, voz, tempo y ambiente. *«bolero romántico con requinto y voz masculina melancólica, tempo lento»* funciona mejor que *«una canción triste sobre la despedida»*.
- **Versos cortos y regulares** (de 6 a 10 sílabas) se cantan mejor. Una estrofa de 4 líneas y un estribillo que se repite dan la estructura más clara.
- Si el estribillo se repite, **escríbelo cada vez** (`[Estribillo]` con su letra otra vez); el modelo no repite solo.
- Para un tema de **más de 2 minutos**, pon la duración: si no, el modelo la ajusta a lo que dure la letra.
- ¿Te gustó una canción pero quieres retocar algo? Pulsa ↻ en la lista: se carga con su semilla. Cambia solo el estilo o una palabra y vuelve a generar: saldrá parecida.
- Para probar varias versiones de la misma letra, deja la semilla en `azar` y genera varias veces; con **Guardar .md…** te quedas con la ficha de la que más te guste (la semilla está en la lista con ↻).

### 8.4 Desde la terminal

```bash
juglar-cola musica "El juglar.md"                     # una canción .md (con Estilo: y la letra)
juglar-cola musica canciones/*.md                     # varias de golpe, una tras otra
juglar-cola musica "El juglar.md" -d "rock épico con guitarras eléctricas"   # mismo texto, otro estilo
juglar-cola musica -d "música medieval de taberna, laúd y flauta" -t 60 -o ~/Música/Juglar/Taberna.mp3   # instrumental
```

`-d` (estilo), `-t` (segundos), `--semilla` e `--idioma` mandan sobre lo que diga el `.md`.
