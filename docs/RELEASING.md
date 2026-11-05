# Выпуск версии

Публикуется **только ветка `prod`**. Workflow `.github/workflows/publish.yml` проверяет, что коммит тега входит
в `prod`, иначе останавливается до сборки.

## Порядок

1. Изменения готовятся в рабочих ветках и сливаются в `prod` через pull request (CI зелёный).
2. В `prod` обновить версию в `tehzor/_version.py` и раздел в `CHANGELOG.md` (`## [X.Y.Z] — дата`).
3. Поставить тег на коммит `prod` и отправить его:

   ```bash
   git tag -a vX.Y.Z -m "tehzor X.Y.Z" origin/prod
   ```

   ```bash
   git push origin vX.Y.Z
   ```

   Или в GitHub: **Releases → Draft a new release → Choose a tag: `vX.Y.Z` (Create new tag) → Target: `prod` →
   Publish release** — workflow запустится так же и дополнит релиз файлами сборки и описанием из CHANGELOG.

4. Workflow: проверки (ruff, mypy, тесты) → тег совпадает с версией → сборка и `twine check` → **ожидание
   подтверждения в среде `pypi`** → публикация на PyPI (Trusted Publishing, без токенов) → GitHub Release с
   разделом CHANGELOG.
5. Проверить: `uvx --from "tehzor[mcp]==X.Y.Z" tehzor-mcp --help`.

Версию, опубликованную на PyPI, перезалить нельзя: ошибка исправляется следующей версией (X.Y.Z+1).

## Настройки GitHub

- **Settings → Environments → `pypi`:** Required reviewers — ответственный за релиз; Deployment branches and
  tags — только теги `v*`.
- **Settings → Rules → Rulesets:**
  - ветка `prod` — запрет удаления и force push, изменения только через pull request;
  - теги `v*` — запрет удаления и перезаписи.
- **PyPI → проект tehzor → Publishing:** Trusted Publisher `gritsyuk/tehzor`, workflow `publish.yml`, среда `pypi`.
