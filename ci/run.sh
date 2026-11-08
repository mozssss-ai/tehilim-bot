#!/bin/sh
# הרצה אחת של הבוט ב-GitLab CI.
# שעות ההרצה מוגדרות ב-forge.py (SCHEDULES). כפתור בדשבורד מפעיל הרצה מיד דרך webhook.
set -u
P=6dd35a90fba60637

publish() {  # מכין את הדשבורד לפרסום ב-GitLab Pages (התיקייה public)
  rm -rf public && mkdir -p public && cp -r docs/. public/
  mkdir -p "public/$P/audio" && cp assets/music/holiday/*.mp3 "public/$P/audio/" 2>/dev/null || true
}
mkdir -p out && rm -f out/failed.txt
step() {  # מריץ שלב; אם נכשל – ממשיכים, והכישלון מוצג בדשבורד
  name="$1"; shift; echo; echo "===== $name"
  "$@" || { echo "!!!!! השלב נכשל: $name"; echo "$name" >> out/failed.txt; }
}

# הרצה מה-webhook שאינה פתיחת בקשה חדשה (למשל סגירה) – לא עושים כלום, רק מפרסמים שוב את הדשבורד
if [ "${CI_PIPELINE_SOURCE:-}" = "trigger" ] && ! python3 forge.py relevant; then
  echo "לא בקשה חדשה – אין מה לעשות."; publish; exit 0
fi

apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends git libfribidi0 libraqm0 >/dev/null
pip install -q --disable-pip-version-check -r requirements.txt
git config user.name "tehilim-bot"
git config user.email "tehilim-bot@noreply.gitlab.com"

# הגדרה ראשונית (שעות הרצה + webhook) – בהרצה ידנית בלבד
if [ "${CI_PIPELINE_SOURCE:-}" = "web" ] || [ "${CI_PIPELINE_SOURCE:-}" = "api" ]; then
  step "הגדרת שעות הרצה" python forge.py setup
fi

step "בקשות מהדשבורד" python forge.py manage

rm -f out/check.env
step "בדיקה אם צריך להעלות" python bot.py --check
if grep -q "post=true" out/check.env 2>/dev/null; then
  WAIT=$(sed -n 's/^wait=//p' out/check.env | tail -1)
  apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null
  [ "${WAIT:-0}" -gt 0 ] 2>/dev/null && sleep "$WAIT"
  step "העלאת הפרק" python bot.py
fi

step "תגובות והודעות" python comments.py
DOW=$(TZ=Asia/Jerusalem date +%u); HOUR=$(TZ=Asia/Jerusalem date +%H)
if [ "$DOW" = "7" ] && [ "$HOUR" -lt 10 ]; then step "למידת שעות" python tune.py; fi
if [ "$DOW" = "1" ] && [ "$HOUR" -lt 10 ]; then step "חידוש מפתח" python refresh_token.py; fi
step "גלריה" python gallery.py
step "ניתוח שיווקי ודשבורד" python marketing.py
step "שומר" python watchdog.py
step "דף מצב" python bot.py --status

echo; echo "===== שמירה"
git add -A state.json STATUS.md replied.json marketing.json dedications.json overrides.json whatsapp.json \
  rec_status.json config.json learn.json usage.json docs 2>/dev/null
if ! git diff --cached --quiet; then
  git commit -q -m "bot update [skip ci]"
  REMOTE="https://oauth2:${GL_TOKEN}@gitlab.com/${CI_PROJECT_PATH}.git"
  ok=0
  for i in 1 2 3; do
    git fetch -q "$REMOTE" main && git rebase -q -X theirs FETCH_HEAD && \
      git push -q -o ci.skip "$REMOTE" HEAD:main && { ok=1; break; }
    git rebase --abort 2>/dev/null; sleep 5
  done
  [ "$ok" = 1 ] && echo "נשמר." || { echo "!!!!! השמירה נכשלה"; publish; exit 1; }
fi
publish
