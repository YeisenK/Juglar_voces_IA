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

**Narradores**

| Voz en la app | Cómo suena |
|---|---|
| Narradora de audiolibros | Mujer ~30, cálida, suave, latina neutra. Pausada y expresiva. |
| Narrador de audiolibros | Hombre ~40, grave, cálido y resonante, latino neutro. |
| Narradora española | Mujer ~35, acento de España, cálida y clara. |
| Narradora de documentales | Mujer ~45, serena, profunda y elegante. |
| Narrador de documentales | Hombre ~55, profundo, sereno, solemne. |

**Voces generales para personajes**

| Voz en la app | Cómo suena |
|---|---|
| Adolescente (chica) | 16 años, clara, enérgica, algo sarcástica. |
| Adolescente (chico) | 16 años, voz que apenas ha cambiado, desafiante. |
| Niña | ~9 años, dulce, aguda, juguetona. |
| Niño | ~8 años, aguda, curiosa, traviesa, rápida. |
| Mujer joven | ~25, clara, natural, decidida. |
| Hombre joven | ~25, natural, cercano, relajado. |
| Mujer (México) | ~30, acento mexicano, cálida y alegre. |
| Hombre (Argentina) | ~35, acento rioplatense, cálido. |
| Hombre (España) | ~40, acento castellano, cercano. |
| Mujer misteriosa | ~40, baja, susurrante, enigmática. |
| Reina | ~55, firme, elegante, fría, de mando. |
| Guerrero | ~35, fuerte, firme, autoritario. |
| Hombre gruñón | ~45, áspero, irritable, brusco. |
| Villano | ~50, muy grave, fría, amenazante, lenta. |
| Anciana | ~75, suave, quebradiza, maternal. |
| Anciano | ~75, grave, ronca, cansada, sabia. |

**Voces de pueblo** (nuevas)

| Voz en la app | Cómo suena |
|---|---|
| Partera vieja | ~75, contralto ronca y potente, mandona y práctica, acento rural. |
| Vieja de pueblo (brava) | ~70, grave, fuerte y rasposa, gritona, ríe a carcajadas. |
| Vieja chismosa | ~70, aguda y algo nasal, rápida, en susurros cómplices. |
| Herrero | ~45, muy grave, potente y ronca, habla alto, bonachón. |
| Campesino | ~55, gastada y cálida, lenta, humilde y desconfiada. |
| Campesina | ~40, clara y fuerte de mercado, respondona y alegre. |
| Tabernero | ~50, ronca y jovial, bromista. |
| Pastor viejo | ~75, suave y cascada, lenta, con pausas largas. |
| Mozo de pueblo | ~16, voz que se quiebra, atropellado y nervioso. |

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
- Leonor, Pedro y Galindo hablan con sus voces; «preguntó» lo dice Leonor por ser corto.
- `---` deja una pausa larga de cambio de escena.

---

## 5. Flujo de trabajo recomendado

1. **Escribe** tu capítulo en un `.md` con las marcas de diálogo.
2. Ábrelo en la pestaña **Leer** (`Ctrl+O`) y mira el panel **Propiedades**: comprueba el reparto y los avisos.
3. Escucha un trozo con **Leer** (`Ctrl+Intro` para leer/pausar, `Esc` para detener).
4. Cuando te guste, pulsa **Exportar a audio…** (`Ctrl+Mayús+E`) o añade el archivo en la pestaña **Exportar**. Se convierte en segundo plano, aunque cierres la ventana.
5. Para audiolibros largos, deja activado **Revisar con Whisper** (pestaña *Audiolibro*): escucha cada fragmento y regenera los que salgan mal.
6. ¿Prisa? Activa **⚡ Modo flash** (arriba en la pestaña *Audiolibro*): no se revisa con Whisper y todo lo lee el narrador; las marcas `—2` y `—@leonor` se quitan y no se leen. También desde la terminal: `md2audio libro.md --flash`.

### Atajos

| Atajo | Acción |
|---|---|
| `Ctrl+Intro` | Leer / pausar |
| `Esc` | Detener |
| `Ctrl+O` | Abrir y leer un archivo |
| `Ctrl+Mayús+E` | Exportar el texto a audio |
| `Ctrl+1` … `Ctrl+4` | Leer · Exportar · Voces · Audiolibro |
