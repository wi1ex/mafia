# Хеллоуинские статусы игроков

Инструмент: встроенный image_gen. Сезонные версии находятся в этой же папке. По просьбе пользователя первый вариант `killPlayer.png` перенесён в `frontend/src/assets/images/killPlayer.png` как постоянный; для Halloween создан отдельный новый вариант. Остальные исходные PNG не изменены. Пиксельная стилистика применяется ко всем персонажам и предметам.

| Файл | Смысл | Сезонная концепция |
|---|---|---|
| fouledPlayer.png | Удалён со стола по фолам | Штрафные карточки и проклятая молния |
| killPlayer.png | Убит мафией ночью | Тыквоголовый мафиози с костлявой рукой, луна, летучая мышь и призрак |
| leavePlayer.png | Совершил самоубийство | Призрак с разбитым символом жизни у собственного надгробия, без показа способа |
| lowSignal.png | Проблемы с сетью | Телефон, оборванный сигнал и разъединённый кабель |
| sleepPlayer.png | Спит | Закрытые глаза, ночной колпак и Z |
| votedPlayer.png | Изгнан голосованием | Урна с бюллетенями и несколько призрачных рук |

## Общий промпт

Use case: style-transfer / precise-object-edit.
Asset type: ONE replacement square pixel-art status illustration inside a player avatar tile in the Russian social game deceit (Mafia).
Input image1 is the current original status illustration, an edit target and source of the SAME recurring player character: young adult male, messy dark hair, pale-warm skin, gray shirt, dark trousers, chunky black shoes. Preserve recognizable identity, pixel density and compact readable game-sprite silhouette; poses/props can change only to clarify the specified state and add Halloween. Input image2 is an approved seasonal cat illustration for PALETTE AND PIXEL EDGE reference only; do NOT put this cat, its hat or umbrella into the player illustration.
STYLE MUST BE ACTUAL PIXEL ART throughout ALL objects: visible small square pixels, stepped diagonals, crisp hard outlines, flat limited palette and blocky dither shading. Every face, hand, prop, light and shadow must follow the same coarse pixel grid. NO smooth vector curves, no photorealism, no glossy 3D, no painterly brushwork, no antialiasing, blur or bloom, no mixing a pixel person with smooth props. Original game sprite style with Halloween charcoal, dark plum, warm burnt orange, pale amber and restrained ghostly teal. Keep skin/body readable. No detailed bloody anatomy, no protruding bullets, no gore.
CANVAS: square approximately1254x1254 (or the available square output), OPAQUE flat solid background exact dark charcoal #171723 across all empty space, matching original tile. Do not put this art on transparent, white, checkerboard or scenery backgrounds. One complete centered scene ONLY, no contact sheet, no border, no title, no UI, no extra words or watermark. Leave breathing room around all sides; main scene occupies central~65-72% of canvas, similar apparent scale to original; no cropped character/limbs/props. Keep most area quiet flat #171723, apart from a tiny understated pixel ground shadow if needed.
READABILITY: status must read at a tiny avatar-tile thumbnail. Clear large silhouette, only2-3 strong meaningful props, few tiny decorative accents. Horror/Halloween via expressive shadowy supernatural props, haunted shapes, mean pumpkin details, ghostly light; not a dense background. The six states form one family but each action must remain unmistakable and visually distinct.
Do not copy unwanted original violence if the specific concept below replaces it. Exact event/state specified below takes priority over misleading props in the old illustration.

## fouledPlayer.png

EVENT: player was REMOVED FROM THE TABLE AS A PENALTY FOR REPEATED FOULS / rule violations.
Keep recognizable frightened player recoiling as a sharp orange CURSE-LIGHTNING strike descends from upper right (echo original lightning theme). At upper left of the character show a clear fan of THREE large red-orange referee penalty cards, each marked with ONE simple black X, a small skeletal referee hand presenting the cards from the side. Cards and thunder together signal punishment for repeated violations. Player upright/stumbling backward with hands raised, dark teal-orange curse sparks, NO death, no grave, no ballot, no human crowd voting, no door/exit. Add a small mean jack-o'-lantern shape subtly worked into the central thunder strike/star. Leave all character proportions consistent with the original. Card X marks may be blocky symbols, no words or numerals. Dominant narrative is penalized/banished by referee, not network electricity.

## killPlayer.png

### Первый вариант — теперь постоянный

Первоначальный промпт ниже относится к одобренной иллюстрации, которая теперь сохранена в `frontend/src/assets/images/killPlayer.png`. После отката Halloween она остаётся постоянной версией.

EVENT: player was KILLED BY THE MAFIA DURING THE NIGHT.
Retain original pixel character at center-right but replace the graphic head wound/protruding bullet with a non-graphic death scene: player's gray-clothed body slumped/fallen at lower center, closed/X eyes small, a wispy pale TEAL GHOST shaped like the same character rising just above the body. At upper-left/left is a LARGE ominous MAFIA silhouette with black fedora, dark coat and bandana, aiming a small pixel revolver toward the victim; muzzle dark or one tiny amber flash, no visible wound or gore. A small amber crescent moon near upper right makes NIGHT clear. Mafia attacker and rising soul are the main clear motifs. ONE scene, no doorway, no cards, no vote hands, no guillotine. Dark threatening Halloween crime vibe. Prefer a complete compact composition with attacker left, fallen character right, small ghost above; keep silhouette readable and avoid overlapping all figures into a mass.

### Новый сезонный вариант

Use case: style-transfer.
Asset type: ONE production-ready square pixel-art Halloween status illustration for killPlayer.png in the fictional Mafia game deceit. Meaning MUST remain unmistakable: PLAYER WAS KILLED BY THE MAFIA AT NIGHT.
Input image 1 is the approved PERMANENT illustration, supplied as STYLE, CHARACTER and QUALITY reference; create a visibly NEW HALLOWEEN composition rather than copying it. Preserve the same recurring adult cartoon victim: messy charcoal hair, warm skin, gray shirt, navy trousers and chunky black shoes. Match the reference's actual square-pixel game-sprite style, readable blocky outlines, scale and sharp stepped shading. Image 2 is only a supporting seasonal PALETTE and PIXEL EDGE reference; do not include its cat/umbrella or lettering.
NEW CONCEPT: a sinister PUMPKIN-HEADED MAFIA ASSASSIN stands on the RIGHT, with a dark fedora tilted over the evil jack-o-lantern face (slanted glowing orange eyes and jagged carved grin), tattered plum-black long mafia coat, one skeletal hand aiming a compact dark revolver down and LEFT toward the fallen victim. The jack-o-lantern head must be the unmistakable Halloween centerpiece while the fedora, coat and revolver clearly identify mafia. A tiny angular amber muzzle flash is enough; no bullet penetration or wound.
At lower LEFT/center lies the same gray-shirted victim with small X eyes, intact body, no blood. Above him a recognizably matching PALE TEAL GHOST rises in a crooked wispy trail, its hands lifted in alarm. Keep ghost and body distinct and readable. A restrained burnt-orange crescent moon and ONE tiny pixel bat at upper LEFT indicate Halloween night. A very small fallen carved pumpkin lantern near the ground may echo the killer's head, but don't crowd the scene. Grim spooky game atmosphere, simple clear silhouettes.
COMPOSITION: complete attacker on right, fallen player at lower left, ghost upper left/center, no overlapping silhouettes obscuring the story; all inside central 70-76% of square canvas with ample empty margins. Match reference apparent character scale; do not cut off feet, hat, ghost, moon, props or coat.
PIXEL ART ONLY throughout: every pumpkin, carved facial feature, skeletal finger, revolver, coat, moon, bat, player, ghost and ground shadow uses the SAME crisp chunky square-pixel grid with stepped diagonals, hard black/dark outlines, flat limited colors and block dither shading. NO smooth vector curves, no glossy 3D, photorealism, painterly brushwork, blur, bloom or anti-aliased edges.
Palette: charcoal, midnight plum, pumpkin burnt orange / amber, restrained spectral teal. Quiet OPAQUE solid exact #171723 empty background matching the original avatar tiles, no scenery, room, graveyard, horizon, heavy vignette, texture, checkerboard or transparent background. Square 1254x1254 if available, one isolated finished scene. No frame, UI, collage, labels, words, lettering or watermark. No gore or graphic injuries. No ballot box, foul cards, cracked heart, grave marker, sleep Z, phone, or door.

## leavePlayer.png

Use case: stylized-concept / style-transfer.
Asset type: ONE square pixel-art in-game status illustration for the fictional Russian Mafia game deceit; file leavePlayer.png, whose game-state meaning is that the player's character died by suicide. This is a fictional game avatar status, not a real-world scene.
Image 1 is a STYLE AND CHARACTER REFERENCE ONLY (sleepPlayer.png): preserve the recurring adult cartoon male character's recognizable messy dark hair, warm skin, gray shirt, navy trousers and chunky black shoes; change his state and pose completely. Image 2 is a PALETTE / PIXEL EDGE reference only (Halloween cat), do not include the cat, hat or umbrella.
Make a grim, symbolic NON-GRAPHIC AFTERMATH with no method depicted: at center a small dark stone grave marker bearing the same player's blocky portrait with small X eyes. His pale teal ghost, recognizably the same messy-haired adult character, hovers beside it looking somberly downward; his own ghostly hands hold the two separated halves of a large cracked pumpkin-orange heart-shaped game-life token. One small extinguished candle and a subdued angry jack-o-lantern sit near the stone. This status symbolizes his OWN ended game life, with no outside killer, no vote or foul penalty and no walking away through an exit. Keep the broken life-token and ghost large, clear and readable. No living sleeping person or Z symbols.
STYLE MUST BE ACTUAL PIXEL ART in every detail: a crisp, chunky square-pixel grid, stepped diagonals, strong blocky dark outlines, flat limited colors and block dither shadows, matching the original game sprite family. Every ghost edge, heart, stone, candle, pumpkin and shadow obeys the same pixel grid. NO photorealism, smooth vector shapes, gradients, blur, bloom, antialiasing, glossy 3D or painted texture.
Palette: charcoal, dark plum, burnt pumpkin orange, restrained ghostly teal. Empty background OPAQUE flat exact #171723; no scene background, floor horizon, vignette, border or UI. Square 1254x1254 if available; main complete scene occupies about central 65-72% with wide quiet margins, nothing cut off. Tiny subtle stepped ground shadow allowed. Same apparent sprite scale as the original, readable at avatar thumbnail.
No text, letters, labels, watermark. No wound, blood, gore, weapon, rope, or self-harm method/action. No attacker, cards, ballot box, door, travel bag, or network symbols. Deliver only one complete production-ready square image.

## lowSignal.png

EVENT: living player has a NETWORK CONNECTION PROBLEM / weak or lost signal.
Keep recognizable worried player upright at left, holding smartphone up trying to catch signal; phone display shows big pixel broken Wi-Fi symbol (curved stepped arcs crossed with a small orange diagonal, NO words). At right show a crooked dark haunted transmission tower / router with antenna, and a clearly BROKEN / unplugged network cable between phone/player side and router with two separated plug halves. Above is large pixel weak Wi-Fi indicator with only one tiny amber bar/dot active, other two bars gray or dashed teal signal fragments visibly interrupted. At most one tiny bat hanging from antenna as Halloween detail, small spiderweb on router corner. Player intact alive, not electrocuted, not sleeping, no attack, no cards or blood. Keep 2main subjects and simple large signal icon rather than busy manyprops. Broken connection reads instantly at thumbnail.

## sleepPlayer.png

EVENT: player is ASLEEP, not dead, and not experiencing network problems.
Close-up of SAME recognizable player's face centered somewhat lower like original, eyes gently CLOSED (normal short closed eyelids, NEVER Xs), relaxed peaceful mouth, small dark plum sleeping cap with crooked tip and tiny pumpkin-orange band or patch. Head resting on a small dark pillow at bottom edge, shoulders just visible. Above right exactly TWO or THREE clear blocky pixel 'Z' sleep symbols in pale teal and orange; these Z symbols are the ONLY text allowed. Small amber crescent moon upperleft and a tiny curled sleeping bat adjacent to moon provide Halloween atmosphere. No huge fear/scared eyes, no wounds, no death body, no spectral soul leaving body. Do not let cap conceal the familiar dark hair, face shape or closed eyelids. Keep props crisp squarepixel edges, even moon, pillow, bat andcap followpixelgrid. Read as quiet spooky slumber.

## votedPlayer.png

EVENT: table collectively VOTED OUT / EXPELLED the player, distinct from referee punishment and from leaving voluntarily.
Show recognizable frightened player mid-stumble in center-right being pushed off the edge of a small dark gaming-table platform toward right by THREE visible ghostly teal skeletal HANDS emerging from the left, clearly collective pointing/pushing. At front-left, below hands, a small prominent pumpkin-orange BALLOT BOX with slit at top and TWO pale paper ballots, each marked with a blocky X, communicates voting. Large hands all point/urge same direction. Rightward thrown pose evokes original kicked-off illustration, but don't use a giant boot as solemeaning. No hanging, no gun, no death wound or gore, no exit door/suitcase, no thunder or referee cardfan. Halloween via skeletal ghost hands, shadowed purple stone/tableedge and an angry carved pumpkin motif onballotbox. Clear contrast: ballotbox+multiplehands for collectiveexpulsion vs foulcards+lightning for rulepenalty.

