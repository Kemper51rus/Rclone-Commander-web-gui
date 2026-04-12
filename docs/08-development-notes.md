# 🛠️ Development Notes

Служебная заметка для разработки. Не пользовательская документация.

---

## UI Tooltip Pattern

В dashboard используется общий tooltip-механизм для элементов интерфейса.

Использование:

```html
<div class="ui-tooltip has-tooltip" data-tooltip="Текст подсказки" tabindex="0">...</div>
```

Правила:

- `ui-tooltip` включает базовый tooltip-стиль
- `has-tooltip` включает hover/focus-поведение
- `data-tooltip` содержит текст подсказки
- `tabindex="0"` нужен, если tooltip должен открываться с клавиатуры

Где сейчас используется:

- status widgets в `taskboard/backend/app/dashboard.html`

Примечание для разработки:

- при добавлении новых tooltip в dashboard нужно переиспользовать этот механизм, а не делать отдельный `title` или новый CSS-стиль

