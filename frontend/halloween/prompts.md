# Выбранный комплект Halloween

Для исходного комплекта использован встроенный image_gen. Серия1 исключена. Позже первые два слайда заменены файлами пользователя без генерации и без редактирования текста (см. раздел замены ниже).

| Ресурс | Выбор |
|---|---|
| Слайд1 | Новое прикреплённое изображение пользователя: две тыквенные монеты |
| Слайд2 | Новое прикреплённое изображение пользователя: трансляции, регистрации и тыква |
| Слайд3 | Серия3 |
| Слайд4 | Серия3 |
| Слайд5 | Серия2 |
| Подписка | Серия2 |
| Обратная связь | Серия3 |

## Замена первых двух слайдов

Файл `codex-clipboard-8f43df6b-548e-46aa-82af-a47709071ab4.png` скопирован как `carousel-image1.png`; `codex-clipboard-b30a4365-9880-4b93-808f-3e6e387559cd.png` — как `carousel-image2.png`. Оба 1448×1086, сохранены побайтно, без image_gen и без изменения надписей. В `theme.css` скрыт повторный HTML-текст слайдов 1–2 и задано вписывание без обрезки. Промпты ниже для этих двух файлов относятся к прежним версиям; слайды 3–7 остаются прежними.

## Общий промпт исходного комплекта

Use case: precise-object-edit. Asset type: ONE final background artwork for an existing Russian gaming website, not a UI mockup, not a moodboard.
Input image 1 is the user's SELECTED concept sheet and the edit target. Extract/reconstruct ONLY the specified panel at full quality as a standalone image. Preserve the selected panel's particular object shapes, material, angle, lighting, palette and mood as closely as possible. The user already selected this image; DO NOT invent a new visual direction. Input image 2 is the old live-site image; use it ONLY to understand the original near-square aspect ratio, brand logo identity and free-space requirements, do not transfer its old teal-purple palette.
Output exactly ONE illustration filling the entire image, with absolutely no sheet titles, panel labels, image border, page surround, arrows, buttons, carousel dots or UI chips. No collages. All typography will be overlaid as real HTML. Therefore REMOVE all marketing text, all text panels' lettering, labels, slogans, body copy and their shadows. Preserve the blank glass plaques themselves when present. The only lettering allowed is the small app name 'deceit' and '9:41' ON the smartphone when this is the smartphone panel. Symbols engraved on objects are allowed. Keep crisp high quality photorealistic glass/copper objects and realistic pumpkins. No crowds of decorations, no castles or large moon.
The illustration is intended for a fixed 607x494 CSS-pixel carousel panel. Generate approximately 1216x992 px, landscape but NEARLY SQUARE, width:height 607:494 = 1.229:1. Do not output a wide 2:1 banner for a carousel slide. Preserve original object proportions while expanding the selected wide concept vertically into this almost square composition. Need empty safe areas at top 0-65 CSS px for existing UI title/tooltip on slides2-5, and bottom 425-494 CSS px for existing carousel navigation (dim unobtrusive background there, no text or main subject).


## carousel-image1.png

Selected panel: TOP LEFT "01 · Знакомство" of collection 02 / ТЁПЛОЕ СВЕЧЕНИЕ. Preserve its dark warm charcoal background with a handful of softly defocused amber light spots, orange glossy tilted eye disc upper left, large faint smoke-glass rectangle with softly rounded corners in center, realistic smiling lit jack-o'-lantern at lower right and tilted orange microphone disc directly to its left. Keep only a few leaves and a subtle warm glow near lower edges. Eye disc near x14%, y19%, pumpkin near x84%, y76%, microphone near x66%, y79%. Blank glass plaque should extend from x12% to92%, y30% to76%. Absolutely no type in the plaque. Its central x20-78%, y34-66% must remain quiet and unoccupied for HTML heading/body text. Preserve the orange brush flourish under the blank text area near x48%,y72% as in selected panel. Calm empty gradient above and behind. No candles or pumpkin overlapping central text space.

## carousel-image2.png

Selected panel: TOP RIGHT "02 · Трансляции" of collection03 / БИРЮЗА И ТЫКВЕННЫЙ. Preserve orange broadcast signal disc upper left and its precise white broadcast icon, central dark glass plaque, THREE small round photorealistic human portrait avatars in orange rim circles across lower-left center (not cartoon characters), orange-lit carved pumpkin to lower right, near-black background with restrained teal rim reflection and amber floor light. Reframe for nearly square panel: broadcast disc near x16%,y24%, blank glass plaque x11-92%,y30-78%, portrait circles horizontally at x34%,46%,58%, all near y65%, pumpkin center x85%,y73%. Leave blank plaque at x31-86%,y35-53% for main HTML copy, and blank strip below avatars x23-73%,y75-80% for HTML registration copy. REMOVE all words and all digits including '1000+'; keep all three avatar circles. No text of any kind.

## carousel-image3.png

Selected panel: MIDDLE LEFT "03 · Статистика" of collection03 / БИРЮЗА И ТЫКВЕННЫЙ. Preserve the big amber-orange copper-glass trophy on the left-center with engraved original deceit symbol; preserve realistically ridged orange jack-o'-lantern at right of trophy base, dark glass achievement cards behind to left and right, small sparse floating gold/copper confetti, near-black background with a dim teal rim and subtle polished floor. Reframe trophy fully visible with both handles at x20-68%, y18-69%; pumpkin near x72%,y62%. Remove the old caption and leave a clean dark area below objects spanning x12-88%, y73-85% for HTML caption. Bottommost navigation area remains quiet. Retain the selected material realism, avoid excessive confetti or new props.

## carousel-image4.png

Selected panel: MIDDLE RIGHT "04 · Комьюнити" of collection03 / БИРЮЗА И ТЫКВЕННЫЙ. Preserve exactly three overlapping, slightly tilted smoke-black glass rounded cards with orange-glowing edges: white people/group icon on LEFT card, white rounded chat bubble with three dots on CENTER card, beautifully carved glowing orange pumpkin face rendered inside/on RIGHT card. Do not add another separate pumpkin alongside: the chosen pumpkin is ON the right card. Dark calm charcoal background, restrained dark teal rim reflection and warm orange light reflected on the floor under cards. Reframe the three cards to occupy x14-88%,y40-76%, with room at x12-88%,y22-34% for two-line HTML caption; remove existing caption. Preserve the short orange brush underline centered near y36%, below blank caption area. Top title safe zone and bottom navigation safe zone empty.

## carousel-image5.png

Selected panel: BOTTOM LEFT "05 · Web App" of collection02 / ТЁПЛОЕ СВЕЧЕНИЕ. Preserve the particular realistic glossy black smartphone entering diagonally from the right, original white geometric deceit mark on an orange rounded square app icon, small deceit app label and 9:41 clock on phone, a blue mail icon lower on phone. Preserve warm blurred amber light spots behind, a small candle at lower left and the softly blurred realistic pumpkin behind lower-left foreground. The chosen pumpkin is in the LOWER LEFT, not covering the phone at right. Adapt to near-square frame with phone starting near x57% at top and spanning right half; left x5-50%,y45-65% remains dark and empty for two-line HTML copy. Keep app icon branded exactly like image2 existing original phone; don't substitute another logo. Remove only marketing caption outside phone. No glass plaque, no new objects. Bottommost 14% dark enough for installed button/navigation.

## carousel-image6.png

OVERRIDE carousel framing: this asset is the SUBSCRIPTION banner in BOTTOM RIGHT upper banner of collection02 / ТЁПЛОЕ СВЕЧЕНИЕ. Produce one wide horizontal background approximately 1216x528 px, target aspect1214:524 (2.317:1). The site crops it to a more panoramic strip, so important subjects must fit within central 65% of height. Preserve the chosen banner exactly in look: almost-black empty left half, amber bokeh and warm candlelit floor, tilted dark glass/copper rounded-square plaque with thin glowing outline and engraved luminous gold-orange CROWN at right, a realistic dark orange pumpkin in front of plaque near x75%, small candle next to it and restrained autumn leaves at bottom right. The CROWN plaque should be large, with upper/right edges allowed outside image boundary. All main objects confined to rightmost 48%. Left x0-55% is quiet deep charcoal for real HTML copy and button. Remove ALL existing words, arrow button and button border. No letters anywhere. Preserve its warm glow and pumpkin/plaque positions rather than redesigning.

## carousel-image7.png

OVERRIDE carousel framing: this asset is CONTACT / "Обратная связь", BOTTOM RIGHT lower banner of collection03 / БИРЮЗА И ТЫКВЕННЫЙ. Produce one wide horizontal background approximately 1216x384 px, target aspect1214:374 (3.246:1), or closest panoramic image. Preserve selected cool turquoise/teal translucent GLASS ENVELOPE floating at right at slight diagonal, realistic glass edge/refraction, warm highlights only on thin edges, empty nearly-black left 60%, small dark rocks along lower right, restrained teal glow under envelope, fine delicate SPIDERWEB in upper-right corner. Envelope center at x81%,y53%, fully visible, size about25% image width and62% image height. No pumpkin, no orange recoloring, no crown. Remove ALL existing words and arrow button/border; leave left side uninterrupted clean dark charcoal for HTML copy/button. Keep the chosen cool teal atmospheric image as closely as possible.

