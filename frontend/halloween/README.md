# Halloween: одна папка со всем комплектом

Все новые файлы находятся в **`frontend/halloween/`**. За её пределами изменены только три ранее существовавших файла:

- `frontend/src/pages/Home.vue`
- `frontend/src/views/Carousel.vue`
- `frontend/vite.config.ts`

Исходные изображения в `frontend/src/assets/images/` сохранены.

## Полный откат к старому дизайну

Сначала прочитайте инструкцию: при удалении папки она тоже исчезнет.

### Простой способ: готовый патч

Выполните из корня репозитория:

```powershell
git apply --check frontend/halloween/rollback.patch
git apply frontend/halloween/rollback.patch
```

Первая команда только проверяет возможность отката. Вторая убирает подключение Halloween из трёх старых файлов. Другие части проекта она не затрагивает. Если проверка сообщает о конфликте с последующими правками, используйте ручной способ ниже.

Затем удалите **только папку `frontend/halloween/` целиком**. После этого:

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Опубликуйте результат обычным способом.

### Ручной способ: что изменить в старых файлах

#### 1. frontend/vite.config.ts

Удалите импорт:

```ts
import halloweenThemePlugin from './halloween/vite-plugin.ts'
```

Из массива `plugins` удалите только строку:

```ts
halloweenThemePlugin(),
```

Остальные настройки оставьте.

#### 2. frontend/src/pages/Home.vue

- Верните корневой элемент к `<main class="card">`: уберите класс `home-page`.
- Удалите импорт `import { useHomeSeason } from '../../halloween/homeSeason'`.
- Удалите строку `const { seasonImage, resetHomeSeason } = useHomeSeason()`.
- Верните два изображения в блоках подписки и обратной связи к следующему виду:

```html
<img class="background-image-6" :src="imageSlide6" alt="" aria-hidden="true" />
<img class="background-image-7" :src="imageSlide7" alt="" aria-hidden="true" />
```

То есть замените `seasonImage(5, imageSlide6)` и `seasonImage(6, imageSlide7)` на `imageSlide6` и `imageSlide7`, а с этих двух тегов уберите `@error="resetHomeSeason"`.

#### 3. frontend/src/views/Carousel.vue

Удалите два импорта:

```ts
import { useHomeSeason } from '../../halloween/homeSeason'
import SeasonalSlideCopy from '../../halloween/SeasonalSlideCopy.vue'
```

Удалите строку:

```ts
const { seasonActive, seasonImage, resetHomeSeason } = useHomeSeason()
```

Верните источники пяти штатных изображений:

| Сейчас | После отката |
|---|---|
| `:src="seasonImage(0, imageSlide1)"` | `:src="imageSlide1"` |
| `:src="seasonImage(1, imageSlide2)"` | `:src="imageSlide2"` |
| `:src="seasonImage(2, imageSlide3)"` | `:src="imageSlide3"` |
| `:src="seasonImage(3, imageSlide4)"` | `:src="imageSlide4"` |
| `:src="seasonImage(4, imageSlide5)"` | `:src="imageSlide5"` |

У этих пяти изображений уберите `@error="resetHomeSeason"`.

Удалите пять строк:

```html
<SeasonalSlideCopy v-if="seasonActive" :slide="1" />
<SeasonalSlideCopy v-if="seasonActive" :slide="2" />
<SeasonalSlideCopy v-if="seasonActive" :slide="3" />
<SeasonalSlideCopy v-if="seasonActive" :slide="4" />
<SeasonalSlideCopy v-if="seasonActive" :slide="5" />
```

Остальные элементы, стили и логику карусели оставьте.

#### 4. Удаление и сборка

Удалите **`frontend/halloween/` целиком**. Других дополнительных файлов или папок Halloween в исходниках нет.

Выполните:

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

После обычной публикации вернётся старый дизайн. Без перечисленных правок удаление исходной папки вызовет ошибку импорта при следующей сборке, поэтому для полного отката нужны оба действия.

## Быстрое отключение на уже работающем сервере

При сборке публикуются семь фоновых PNG, четыре декоративных ресурса (два PNG и два SVG), `manifest.json` и `theme.css` по прежнему адресу `/seasonal/halloween/`. Инструкция, патч, тесты, промпты и исходные TS-файлы туда не копируются.

Удаление опубликованной папки `seasonal/halloween/` и обновление страницы возвращают штатное оформление без пересборки. В текущем контейнере Nginx папка находится в `/usr/share/nginx/html/seasonal/halloween/`.

Это временное отключение до следующего развёртывания из прежнего образа. Для постоянного полного отката выполните раздел выше. Удаление только локальной папки не меняет уже запущенный контейнер.

## Что находится в этой папке

- `carousel-image1.png` … `carousel-image7.png` — пять слайдов, подписка и обратная связь.
- `button-fingers.png` — прозрачные пальцы, держащие кнопку создания комнаты.
- `button-web.svg` — паутинка в углу рядом с кнопкой.
- `logo-halloween.svg` — исходные контуры логотипа с кровавыми краями и потёками.
- `evil-pumpkin.png` — злая тыква справа от логотипа.
- `button-logo-preview.png` — крупный предпросмотр двух изменённых элементов.
- `button-logo-prompts.md` — промпты генерации прозрачных украшений.
- `theme.css` — все дополнительные цвета и положение текста.
- `manifest.json` — состав темы и версия ресурсов.
- `homeSeason.ts` — загрузчик и автоматический возврат к штатным ресурсам при ошибках.
- `SeasonalSlideCopy.vue` — все дополнительные текстовые элементы слайдов.
- `vite-plugin.ts` — подключение этой папки к dev-серверу и сборке.
- `check-home-season.mjs` — проверки включения темы, отключения и недоступных ресурсов.
- `preview.html` — локальное превью комплекта; откройте файл в браузере.
- `prompts.md` — выбор серий и использованные промпты.
- `rollback.patch` — готовые правки трёх старых файлов для полного отката.
- `README.md` — эта инструкция.

Сборочные файлы в `frontend/dist/` создаются обычной командой сборки и не являются дополнительными исходниками.

## Проверки и обновление

Из корня репозитория:

```powershell
node frontend/halloween/check-home-season.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

При замене картинок или CSS меняйте `revision` в `manifest.json`. Отсутствие манифеста отключает тему даже при наличии старых картинок в кеше. Все семь фоновых изображений, четыре декоративных ресурса и CSS должны загрузиться успешно, прежде чем оформление включится. Если один из них недоступен, возвращаются штатные изображения и стили; при сбросе также удаляются CSS-переменные украшений.

## Варианты оформления остальной части главной страницы

- `home-options.html` — локальный просмотр трёх вариантов с переключением цветов и материалов.
- `home-concept-quiet.png` — «Тихие акценты».
- `home-concept-glass.png` — «Тёмное стекло».
- `home-concept-details.png` — «Хеллоуинские детали».
- `home-concepts-prompts.md` — использованные промпты image_gen.

Это макеты для выбора. Они не изменяют активный `theme.css` и не публикуются вместе с ресурсами темы. Все файлы остаются внутри единственной папки `frontend/halloween/` и удаляются вместе с ней при откате.
